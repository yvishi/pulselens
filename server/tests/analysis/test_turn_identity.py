import importlib.util
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from pulselens.analysis.checks import turn_identity
from pulselens.analysis.thresholds import PROVISIONAL, Thresholds, _read
from pulselens.analysis.vision import arcface
from pulselens.analysis.vision.face import GEOMETRY_PAIRS, face_geometry
from tests.fixtures.synth import synthetic_landmarks

HAS_ORT = importlib.util.find_spec("onnxruntime") is not None
REAL_GET_MODEL = arcface.get_model


@pytest.fixture(autouse=True)
def no_arcface(monkeypatch):
    """The proportions rule, the same on every machine: ArcFace is installed per machine (research-only model).
    Tests of the ArcFace path set their own model."""
    monkeypatch.setattr(arcface, "get_model", lambda: None)


def _one(ctx):
    results = turn_identity.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "turn.identity" and r.family == "D" and r.vote_group == "D.identity"
    return r


def test_proportions_ignore_scale_position_and_roll() -> None:
    lm = synthetic_landmarks()
    g = face_geometry(lm)
    assert g.shape == (len(GEOMETRY_PAIRS),) and np.isfinite(g).all() and (g > 0).all()
    c, s = np.cos(0.3), np.sin(0.3)
    moved = {i: (2 * (c * x - s * y) + 40, 2 * (s * x + c * y) - 15) for i, (x, y) in lm.items()}
    assert face_geometry(moved) == pytest.approx(g)
    assert np.isnan(face_geometry({})).all()


@pytest.mark.parametrize("direction", ["left", "right"])
def test_the_same_face_through_the_turn_is_not_flagged(synth, direction: str) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn=direction))
    assert r.status == "usable" and not r.flag and r.reason_codes == [], r.explanation
    assert r.features["change"] < 0.01 and r.risk < 0.05
    assert r.features["frames_before"] >= 5 and r.features["frames_after"] >= 5


def test_a_face_that_comes_back_with_other_proportions_is_flagged(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", identity_scale=1.25))
    assert r.status == "usable" and r.flag and r.reason_codes == ["turn.identity_change"], r.explanation
    assert r.features["change"] == pytest.approx(0.25, abs=0.01)
    assert r.risk == pytest.approx(0.5 * r.features["change"] / 0.15)


def test_a_small_change_stays_under_the_limit(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", identity_scale=1.05))
    assert r.status == "usable" and not r.flag and 0.02 < r.features["change"] < 0.15


def test_no_frontal_frames_after_the_turn_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", turn_returns=False))
    assert r.status == "abstain" and not r.flag and r.reason_codes == ["turn.no_frontal"]
    assert r.features["frames_after"] < 5


@pytest.mark.parametrize("arcface_on", [False, True])
def test_a_turn_not_performed_abstains_instead_of_comparing(synth, monkeypatch, arcface_on: bool) -> None:
    # S2: a still OBS virtual camera image never turned, yet scored "same face" and made family D look covered.
    if arcface_on:
        monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(SidesNet(_axis(0), _axis(0))))
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", turn_followed=False))
    assert r.status == "abstain" and not r.flag and r.risk is None, r.explanation
    assert r.reason_codes == ["turn.not_performed"] and "did not turn" in r.explanation
    assert r.features["peak_deg"] < Thresholds.load().param("turn.follow", "min_peak_deg")


def test_no_face_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", face_in_frames=False))
    assert r.status == "abstain" and not r.flag and "quality.no_face" in r.reason_codes


def test_no_turn_step_is_not_run(synth) -> None:
    assert turn_identity.run(synth.context(kind="genuine", turn=None)) == []


# --- ArcFace (G10c) ---------------------------------------------------------------------------------------------


class SidesNet:
    """Stands in for the network: the first call (the frames before the turn) returns `before`, later calls `after`,
    one row per crop; it remembers what it was shown."""

    def __init__(self, before: np.ndarray, after: np.ndarray) -> None:
        self.rows = [before, after]
        self.inputs: list[np.ndarray] = []

    def __call__(self, x: np.ndarray) -> np.ndarray:
        self.inputs.append(x)
        return np.tile(self.rows[min(len(self.inputs), 2) - 1], (len(x), 1))


def _axis(k: int, d: int = 512) -> np.ndarray:
    e = np.zeros(d, dtype=np.float32)
    e[k] = 3.0  # not unit length: embed() normalises
    return e


def _face_points(scale: float = 2.0, shift: tuple[float, float] = (40.0, 25.0)) -> dict[int, tuple[float, float]]:
    """MediaPipe landmarks whose 5 alignment points are the ArcFace template, scaled and shifted."""
    (ex0, ey0), (ex1, ey1), nose, m0, m1 = ((float(x), float(y)) for x, y in arcface.TEMPLATE * scale + shift)
    return {33: (ex0 - 6, ey0), 133: (ex0 + 6, ey0), 263: (ex1 + 6, ey1), 362: (ex1 - 6, ey1), 1: nose,
            61: m0, 291: m1}


def test_five_points_are_in_template_order_on_a_mirrored_face_too() -> None:
    pts = _face_points()
    p = arcface.five_points(pts)
    assert p.shape == (5, 2) and p.dtype == np.float32
    assert p == pytest.approx(arcface.TEMPLATE * 2 + np.array([40.0, 25.0]), abs=1e-3)
    q = arcface.five_points({i: (300 - x, y) for i, (x, y) in pts.items()})
    assert q[0, 0] < q[1, 0] and q[3, 0] < q[4, 0]  # image-left eye and mouth corner first
    assert q[:, 1] == pytest.approx(p[[1, 0, 2, 4, 3], 1], abs=1e-3)
    assert arcface.five_points({k: v for k, v in pts.items() if k != 1}) is None


def test_alignment_maps_the_points_onto_the_112_template() -> None:
    rgb = np.zeros((300, 320, 3), dtype=np.uint8)
    pts = _face_points()
    cv2.circle(rgb, (round(pts[1][0]), round(pts[1][1])), 3, (255, 255, 255), -1)
    crop = arcface.align(rgb, arcface.five_points(pts))
    assert crop.shape == (112, 112, 3) and crop.dtype == np.uint8
    ys, xs = np.nonzero(crop[..., 0] > 128)  # the dot at the nose tip lands on the template's nose
    assert xs.mean() == pytest.approx(arcface.TEMPLATE[2, 0], abs=1.0)
    assert ys.mean() == pytest.approx(arcface.TEMPLATE[2, 1], abs=1.0)


def test_network_input_is_rgb_nchw_scaled_to_plus_minus_one() -> None:
    crop = np.zeros((112, 112, 3), dtype=np.uint8)
    crop[..., 0] = 255
    x = arcface.to_input([crop, crop])
    assert x.shape == (2, 3, 112, 112) and x.dtype == np.float32
    assert x[:, 0].min() == 1.0 and x[:, 1].max() == -1.0 and x[:, 2].max() == -1.0


def test_embeddings_are_l2_normalised_and_similarity_is_cosine() -> None:
    model = arcface.ArcFaceModel(lambda x: np.tile(np.arange(1.0, 513.0), (len(x), 1)))
    e = model.embed([np.zeros((112, 112, 3), dtype=np.uint8)] * 3)
    assert e.shape == (3, 512) and np.linalg.norm(e, axis=1) == pytest.approx(1.0)
    assert arcface.similarity(e, e) == pytest.approx(1.0)
    a, b = np.eye(4)[:1], np.eye(4)[1:2]
    assert arcface.similarity(a, b) == pytest.approx(0.0) and arcface.similarity(a, -a) == pytest.approx(-1.0)


def test_missing_model_gives_none(tmp_path: Path) -> None:
    assert arcface.ArcFaceModel.load(tmp_path / "w600k_r50.onnx") is None
    assert REAL_GET_MODEL(tmp_path / "w600k_r50.onnx") is None


@pytest.mark.skipif(not HAS_ORT, reason="onnxruntime not installed")
def test_a_broken_model_file_gives_no_model(tmp_path: Path) -> None:
    path = tmp_path / "w600k_r50.onnx"
    path.write_bytes(b"not a model")
    assert arcface.ArcFaceModel.load(path) is None


@pytest.mark.parametrize("direction", ["left", "right"])
def test_the_same_embedding_through_the_turn_is_not_flagged(synth, monkeypatch, direction: str) -> None:
    net = SidesNet(_axis(0), _axis(0))
    monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(net))
    r = _one(synth.context(kind="genuine", n_colour=0, turn=direction))
    assert r.status == "usable" and not r.flag and r.reason_codes == [], r.explanation
    assert r.features["arcface_similarity"] == pytest.approx(1.0) and r.risk == pytest.approx(0.0)
    assert r.features["arcface_before"] == r.features["arcface_after"] == 6
    assert "change" in r.features and "Face recognition" in r.explanation
    assert [x.shape for x in net.inputs] == [(6, 3, 112, 112)] * 2


def test_a_different_person_after_the_turn_is_flagged(synth, monkeypatch) -> None:
    monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(SidesNet(_axis(0), _axis(1))))
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left"))
    min_sim = Thresholds.load().param("turn.identity", "min_similarity")
    assert r.status == "usable" and r.flag and r.reason_codes == ["turn.identity_mismatch"], r.explanation
    assert r.features["arcface_similarity"] == pytest.approx(0.0)
    assert r.risk == pytest.approx(min(1.0, 0.5 / (1 - min_sim))) and r.risk > 0.75


def test_arcface_decides_even_when_the_proportions_changed(synth, monkeypatch) -> None:
    monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(SidesNet(_axis(0), _axis(0))))
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", identity_scale=1.25))
    assert r.status == "usable" and not r.flag and r.features["change"] == pytest.approx(0.25, abs=0.01)


def test_too_few_embedded_frames_fall_back_to_the_proportions(synth, monkeypatch) -> None:
    monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(SidesNet(_axis(0), _axis(1))))
    ctx = synth.context(kind="genuine", n_colour=0, turn="left", identity_scale=1.25)
    full = _read(PROVISIONAL)
    ctx.thresholds = Thresholds({**full, "turn.identity": {**full["turn.identity"], "arcface_min_frames": 7}})
    r = _one(ctx)
    assert r.flag and r.reason_codes == ["turn.identity_change"] and "arcface_similarity" not in r.features


def test_a_failing_model_run_falls_back_to_the_proportions(synth, monkeypatch) -> None:
    def boom(x: np.ndarray) -> np.ndarray:
        raise RuntimeError("onnxruntime failed")

    monkeypatch.setattr(arcface, "get_model", lambda: arcface.ArcFaceModel(boom))
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left"))
    assert r.status == "usable" and not r.flag and "arcface_similarity" not in r.features


def test_the_similarity_limit_sits_between_different_people_and_genuine_set_a() -> None:
    # Genuine set A (one person, laptop webcam): 0.81 to 0.98 before vs after the turn; different people score < 0.3.
    min_sim = Thresholds.load().param("turn.identity", "min_similarity")
    assert 0.3 <= min_sim <= 0.81 - 0.3


@pytest.mark.skipif(not arcface.WEIGHTS.exists() or not HAS_ORT, reason="ArcFace model not installed")
def test_the_real_model_embeds_12_crops_within_2_s() -> None:
    model = arcface.ArcFaceModel.load(arcface.WEIGHTS)
    assert model is not None
    crops = [np.random.default_rng(k).integers(0, 255, (112, 112, 3), dtype=np.uint8) for k in range(12)]
    start = time.perf_counter()
    e = model.embed(crops)
    assert time.perf_counter() - start < 2
    assert e.shape == (12, 512) and np.linalg.norm(e, axis=1) == pytest.approx(1.0)
    assert arcface.similarity(e[:1], model.embed(crops[:1])) == pytest.approx(1.0, abs=1e-4)
