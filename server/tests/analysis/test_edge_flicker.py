import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from pulselens.analysis.checks import visual_edge_flicker
from pulselens.analysis.thresholds import PROVISIONAL, Thresholds, _read
from pulselens.bundle import load_bundle

REAL_NOISE = 0.02  # about 4-5 8-bit codes, like a webcam (G8)


def _one(ctx):
    results = visual_edge_flicker.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "visual.edge_flicker" and r.family == "D" and r.vote_group == "D.edge"
    return r


@pytest.mark.parametrize("noise", [0.003, REAL_NOISE])
def test_a_genuine_face_changes_as_much_at_its_edge_as_in_its_middle(synth, noise: float) -> None:
    r = _one(synth.context(kind="genuine", noise=noise))
    assert r.status == "usable" and r.risk == 0 and not r.flag and r.reason_codes == [], r.explanation
    assert r.features["edge_inner_ratio"] == pytest.approx(1.0, abs=0.1)
    assert r.features["frames"] >= 20 and not r.voting


def test_a_flickering_edge_is_high_risk_but_measured_only(synth) -> None:
    ctx = synth.context(kind="genuine", edge_flicker=0.02)
    r = _one(ctx)
    assert r.status == "usable" and r.features["edge_inner_ratio"] > 2.5, r.explanation
    assert r.risk >= ctx.thresholds.flag_at("visual.edge_flicker")
    assert r.reason_codes == ["visual.edge_flicker_high"]
    assert not r.flag and not r.voting  # measured, not voting: it can never flag yet


def test_the_shipped_thresholds_keep_it_measured_only() -> None:
    assert Thresholds.load().voting("visual.edge_flicker") is False


def test_it_would_flag_once_voting(synth) -> None:
    ctx = synth.context(kind="genuine", edge_flicker=0.02)
    raw = _read(PROVISIONAL)
    raw["visual.edge_flicker"] = {k: v for k, v in raw["visual.edge_flicker"].items() if k != "voting"}
    ctx.thresholds = Thresholds(raw)
    r = _one(ctx)
    assert r.flag and r.voting


@pytest.mark.parametrize("code", ["quality.no_face", "quality.too_dark", "quality.clipped", "quality.moving"])
def test_a_face_that_cannot_be_seen_or_holds_not_still_abstains(synth, code: str) -> None:
    ctx = synth.context(kind="genuine", edge_flicker=0.02)
    ctx.quality.overall.reasons.append(code)
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == [code] and not r.flag and r.risk is None


def test_no_face_in_the_video_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", face_in_frames=False))
    assert r.status == "abstain" and "quality.no_face" in r.reason_codes


def test_heavy_compression_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", jpeg_quality=50))
    assert r.status == "abstain" and r.reason_codes == ["quality.heavy_compression"]


def test_too_few_still_frames_abstain(synth) -> None:
    ctx = synth.context(kind="genuine", edge_flicker=0.02)
    ctx.face_box[30:] = np.nan
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.too_few_frames"] and r.features["frames"] < 20


def test_a_missing_threshold_abstains_instead_of_raising(synth) -> None:
    ctx = synth.context(kind="genuine")
    raw = _read(PROVISIONAL)
    del raw["visual.edge_flicker"]
    ctx.thresholds = Thresholds(raw)
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.check_error"]


def test_speed_at_640x480(synth, tmp_path: Path) -> None:
    """Under 2 s for a whole session at 640x480 (the check decodes its own frames). build_context has read every frame
    before the check runs, so the files are read once first here too: the first read of a freshly written file is
    slow on Windows (3.8 s cold vs 0.4 s warm for this session)."""
    ctx = synth.context(kind="genuine", fps=33.0)
    src = synth.session(kind="genuine", fps=33.0)
    big = tmp_path / src.name
    shutil.copytree(src, big)
    for f in (big / "frames").iterdir():
        img = cv2.resize(cv2.imread(str(f)), (640, 480), interpolation=cv2.INTER_LINEAR)
        f.write_bytes(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes())
    ctx.bundle = load_bundle(big)  # landmarks are normalised, so the cache still fits
    assert ctx.n >= 440
    for f in ctx.bundle.frames:
        ctx.bundle.read_frame(f.idx)
    t0 = time.perf_counter()
    r = _one(ctx)
    elapsed = time.perf_counter() - t0
    assert r.status == "usable" and r.risk == 0, r.explanation
    assert elapsed < 2.0, f"{elapsed:.2f} s"
