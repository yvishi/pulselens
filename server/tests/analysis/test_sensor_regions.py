import numpy as np
import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks import sensor_regions
from pulselens.analysis.thresholds import PROVISIONAL, Thresholds, _read
from pulselens.analysis.vision.noise import robust_sigma
from tests.fixtures.synth import H

REAL_NOISE = 0.02  # about 4-5 codes of 8-bit noise, like a webcam; the default 0.003 sits under the 8-bit rounding


def _one(ctx):
    results = sensor_regions.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "sensor.regions" and r.family == "B" and r.vote_group == "B.regions"
    return r


def test_equal_noise_is_not_flagged(synth) -> None:
    r = _one(synth.context(kind="genuine", noise=REAL_NOISE))
    assert r.status == "usable" and not r.flag and r.risk == 0, r.explanation
    assert r.features["noise_face_neck_ratio"] == pytest.approx(1, abs=0.15)
    assert r.features["noise_face_bg_ratio"] == pytest.approx(1, abs=0.15)
    assert "hypothesis" in r.explanation


@pytest.mark.parametrize("gain", [0.25, 4.0])
def test_a_face_4x_smoother_or_noisier_than_the_neck_is_noted_and_flags_once_voting(synth, gain: float) -> None:
    ctx = synth.context(kind="genuine", noise=REAL_NOISE, face_pixel_noise_gain=gain)
    r = _one(ctx)  # measured, not voting until calibrated (S2: real faces were up to 5.4x their shirt)
    assert not r.flag and r.risk >= 0.5 and r.reason_codes == ["sensor.regions_mismatch"], r.explanation
    full = _read(PROVISIONAL)
    ctx.thresholds = Thresholds(full, {"sensor.regions": {"voting": True}})
    r = _one(ctx)
    assert r.flag and r.reason_codes == ["sensor.regions_mismatch"]
    assert r.features["noise_face_neck_ratio"] == pytest.approx(gain, rel=0.25)


def test_a_background_unlike_the_face_is_reported_not_scored(synth) -> None:
    ctx = synth.context(kind="genuine", noise=REAL_NOISE)
    ctx.noise["background"] = ctx.noise["background"] / 6  # S2: a real room was 6.1x quieter than the face
    r = _one(ctx)
    assert r.status == "usable" and not r.flag and r.risk == 0, r.explanation
    assert r.features["noise_face_bg_ratio"] == pytest.approx(6, rel=0.2) and "reported only" in r.explanation


def test_a_face_within_2_5x_is_not_flagged(synth) -> None:
    r = _one(synth.context(kind="genuine", noise=REAL_NOISE, face_pixel_noise_gain=0.6))
    assert r.status == "usable" and not r.flag


def test_a_hidden_neck_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", noise=REAL_NOISE, chin_y=H - 4))
    assert r.status == "abstain" and r.reason_codes == ["quality.neck_hidden"] and not r.flag


def test_a_moving_face_abstains(synth) -> None:
    ctx = synth.context(kind="genuine", noise=REAL_NOISE)
    ctx.quality.overall.reasons.append("quality.moving")
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.moving"]


def test_too_few_still_frames_abstain(synth) -> None:
    ctx = synth.context(kind="genuine", noise=REAL_NOISE)
    ctx.noise["face"][10:] = np.nan
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.too_few_frames"]


def test_still_frames_leave_out_every_step(synth) -> None:
    ctx = synth.context(kind="genuine")
    still = sensor_regions.still_frames(ctx)
    assert 0 < still.sum() < ctx.n
    for e in ctx.bundle.events:
        inside = (ctx.t >= e.painted_t_ms) & (ctx.t <= e.ended_t_ms)
        assert not still[inside].any(), e.step_id


def test_robust_sigma_reads_small_integer_noise() -> None:
    # Frame differences are integer codes; a MAD would snap to 0 or 1 code here (0 at sigma 0.3, where most are 0).
    rng = np.random.default_rng(0)
    for sigma, rel in ((0.3, 0.25), (0.6, 0.1), (1.0, 0.1), (3.0, 0.1)):
        x = np.round(rng.normal(0, sigma, 50_000))
        expected = np.sqrt(sigma**2 + 1 / 12)  # rounding adds a uniform 1/12 code^2
        assert robust_sigma(x) == pytest.approx(expected, rel=rel), sigma


def test_robust_sigma_ignores_a_few_moving_pixels() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1.0, 10_000)
    x[:300] += 40.0  # 3% of the pixels moved
    assert robust_sigma(x) == pytest.approx(1.0, rel=0.15)


def test_analyze_runs_the_new_sensor_checks(synth) -> None:
    ids = {r.check_id for r in analyze(synth.session(kind="genuine"))}
    assert {"sensor.mode_probe", "sensor.regions", "sensor.prnu"} <= ids
