import importlib.util
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from pulselens.analysis.checks import visual_sbi
from pulselens.analysis.checks.sensor_regions import still_frames
from pulselens.analysis.vision import sbi

HAS_TORCH = all(importlib.util.find_spec(m) for m in ("torch", "efficientnet_pytorch"))


def _one(ctx):
    results = visual_sbi.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "visual.sbi" and r.family == "D" and r.vote_group == "D.detector"
    return r


class FakeNet:
    """Stands in for the network: P(fake) = the crop's mean brightness, and remembers what it was shown."""

    def __init__(self) -> None:
        self.inputs: list[np.ndarray] = []

    def __call__(self, x: np.ndarray) -> np.ndarray:
        self.inputs.append(x)
        return x.mean(axis=(1, 2, 3))


def test_missing_weights_abstains(synth, monkeypatch, tmp_path: Path) -> None:
    assert sbi.SbiModel.load(tmp_path / "FFc23.tar") is None
    monkeypatch.setattr(sbi, "get_model", lambda: None)
    r = _one(synth.context(kind="genuine", turn=None, n_colour=2))
    assert r.status == "abstain" and r.reason_codes == ["visual.model_missing"] and not r.flag
    assert r.explanation == "SBI weights not installed."


def test_scores_shape_and_input_with_a_fake_model(synth, monkeypatch) -> None:
    net = FakeNet()
    monkeypatch.setattr(sbi, "get_model", lambda: sbi.SbiModel(net))
    r = _one(synth.context(kind="genuine"))
    assert r.status == "usable" and r.features["crops"] == 8
    x = net.inputs[0]
    assert x.shape == (8, 3, 380, 380) and x.dtype == np.float32 and 0 <= x.min() and x.max() <= 1
    assert r.risk == pytest.approx(r.features["sbi_top3"])
    assert r.features["sbi_max"] >= r.features["sbi_top3"] >= r.features["sbi_mean"] - 1e-12
    assert "benchmark-trained" in r.explanation and "Indian device streams" in r.explanation


def test_a_high_score_is_flagged_and_a_low_one_is_not(synth, monkeypatch) -> None:
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    monkeypatch.setattr(sbi, "get_model", lambda: sbi.SbiModel(lambda x: np.full(len(x), 0.9)))
    r = _one(ctx)
    assert r.flag and r.risk == pytest.approx(0.9) and r.reason_codes == ["visual.sbi_high"]
    monkeypatch.setattr(sbi, "get_model", lambda: sbi.SbiModel(lambda x: np.full(len(x), 0.1)))
    r = _one(ctx)
    assert not r.flag and r.reason_codes == []


def test_risk_is_the_mean_of_the_top_three(synth, monkeypatch) -> None:
    scores = np.array([0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.0, 0.05])
    monkeypatch.setattr(sbi, "get_model", lambda: sbi.SbiModel(lambda x: scores[: len(x)]))
    r = _one(synth.context(kind="genuine"))
    assert r.risk == pytest.approx(0.8) and r.features["sbi_mean"] == pytest.approx(scores.mean())


def test_fewer_than_four_face_frames_abstain(synth, monkeypatch) -> None:
    monkeypatch.setattr(sbi, "get_model", lambda: sbi.SbiModel(FakeNet()))
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    ctx.face_box[3:] = np.nan
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.no_face"]


def test_crops_come_from_still_face_frames_spread_over_the_session(synth) -> None:
    ctx = synth.context(kind="genuine")
    picked = visual_sbi.pick_frames(ctx, 8, 20.0)
    assert len(picked) == 8 and len(set(picked.tolist())) == 8
    assert still_frames(ctx)[picked].all()
    assert picked.max() - picked.min() > ctx.n / 2


def test_the_crop_matches_sbi_test_phase_geometry() -> None:
    rgb = np.random.default_rng(0).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    out = sbi.crop(rgb, (100.0, 50.0, 80.0, 120.0))
    # SBI: margins w/8 left and right, h/8 top and bottom, int() and +1 at the far edges, then a plain resize.
    expected = cv2.resize(rgb[35:186, 90:191], dsize=(380, 380))
    assert out.shape == (380, 380, 3) and np.array_equal(out, expected)


def test_a_crop_at_the_frame_edge_is_clipped() -> None:
    rgb = np.zeros((240, 320, 3), dtype=np.uint8)
    assert sbi.crop(rgb, (280.0, 200.0, 60.0, 60.0)).shape == (380, 380, 3)


@pytest.mark.skipif(not HAS_TORCH, reason="torch / efficientnet_pytorch not installed")
def test_a_checkpoint_in_sbi_format_loads_and_scores(tmp_path: Path) -> None:
    # SBI saves {"model": Detector().state_dict()}: keys prefixed "net.". A random network, no download.
    import torch
    from efficientnet_pytorch import EfficientNet

    net = EfficientNet.from_name("efficientnet-b4", num_classes=2)
    path = tmp_path / "FFc23.tar"
    torch.save({"model": {f"net.{k}": v for k, v in net.state_dict().items()}}, path)
    model = sbi.SbiModel.load(path)
    assert model is not None
    crops = [np.full((380, 380, 3), v, dtype=np.uint8) for v in (40, 200)]
    p = model.score(crops)
    assert p.shape == (2,) and np.all((p >= 0) & (p <= 1))


@pytest.mark.skipif(not HAS_TORCH, reason="torch / efficientnet_pytorch not installed")
def test_a_broken_checkpoint_gives_no_model(tmp_path: Path) -> None:
    path = tmp_path / "FFc23.tar"
    path.write_bytes(b"not a checkpoint")
    assert sbi.SbiModel.load(path) is None


@pytest.mark.skipif(not sbi.WEIGHTS.exists() or not HAS_TORCH, reason="SBI weights not installed")
def test_the_real_weights_score_8_crops_within_10_s() -> None:
    model = sbi.SbiModel.load(sbi.WEIGHTS)
    assert model is not None
    crops = [np.random.default_rng(k).integers(0, 255, (380, 380, 3), dtype=np.uint8) for k in range(8)]
    start = time.perf_counter()
    p = model.score(crops)
    assert time.perf_counter() - start < 10
    assert p.shape == (8,) and np.all((p >= 0) & (p <= 1))
