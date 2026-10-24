"""PRNU: the vision tests are ported from the old repo; the check is tested on injected fingerprints, because the
synthetic sessions draw their noise from a fixed bank (a pattern by construction)."""

import cv2
import numpy as np
import pytest

from pulselens.analysis.checks import sensor_prnu
from pulselens.analysis.thresholds import Thresholds
from pulselens.analysis.vision.prnu import Fingerprint, fingerprint

H, W = 240, 320
PATTERN = np.random.default_rng(7).normal(0, 0.02, (H, W))  # a sensor's fixed pixel pattern, 2%


def smooth_scene(seed: int) -> np.ndarray:
    s = cv2.GaussianBlur(np.random.default_rng(seed).uniform(0, 1, (H, W)), (0, 0), 10)
    return (s - s.min()) / (s.max() - s.min()) * 0.5 + 0.25


def jpeg(grey: np.ndarray, q: int = 95) -> np.ndarray:
    img = np.clip(np.repeat(grey[..., None], 3, 2) * 255, 0, 255).astype(np.uint8)
    return cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)


def fp_frames(pattern: bool, static: bool, n: int = 40):
    rng = np.random.default_rng(1)
    for i in range(n):
        s = smooth_scene(0 if static else i)
        yield jpeg(s * (1 + (PATTERN if pattern else 0)) + rng.normal(0, 0.01, (H, W)))


def test_a_fixed_sensor_pattern_gives_a_high_pce() -> None:
    fp = fingerprint(fp_frames(pattern=True, static=False))
    assert fp is not None and fp.pce > 1000 and fp.frames == 40


def test_no_pattern_gives_a_low_pce() -> None:
    fp = fingerprint(fp_frames(pattern=False, static=False))
    assert fp is not None and fp.pce < 10


def test_a_static_scene_with_no_pattern_cannot_fake_one() -> None:
    fp = fingerprint(fp_frames(pattern=False, static=True))
    assert fp is not None and fp.pce < 50


def test_too_few_or_too_dark_frames_give_no_fingerprint() -> None:
    assert fingerprint(fp_frames(pattern=True, static=False, n=20)) is None
    assert fingerprint(np.zeros((H, W, 3), dtype=np.uint8) for _ in range(40)) is None


def _one(ctx):
    results = sensor_prnu.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "sensor.prnu" and r.family == "B" and r.vote_group == "B.prnu"
    return r


@pytest.mark.parametrize(("pce", "risk"), [(12.0, 1.0), (500.0, 0.0)])
def test_the_check_reports_the_pce_and_never_flags(synth, pce: float, risk: float) -> None:
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    ctx.fingerprint = Fingerprint(pce=pce, frames=60, skipped=0)
    r = _one(ctx)
    assert r.status == "usable" and r.risk == risk and not r.flag
    assert r.features["pce"] == pce and "never a flag" in r.explanation
    assert ("sensor.prnu_weak" in r.reason_codes) == (risk == 1.0)


def test_flag_stays_false_even_if_the_thresholds_say_it_votes(synth) -> None:
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    ctx.thresholds = Thresholds({"sensor.prnu": {"flag_at": 0.5, "voting": True, "min_pce": 50}})
    ctx.fingerprint = Fingerprint(pce=3.0, frames=60, skipped=0)
    assert not _one(ctx).flag


def test_no_fingerprint_abstains(synth) -> None:
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    ctx.fingerprint = None
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.too_few_frames"] and r.risk is None
