import numpy as np
import pytest

from pulselens.analysis.checks import pulse_coherence
from pulselens.analysis.vision.pulse import pos, snr_and_coherence

FS = 30.0
SKIN = np.array([0.28, 0.18, 0.136])
PBV = np.array([0.33, 0.77, 0.53])


def _skin(hz: float, noise: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(0, 13.5, 1 / FS)
    return SKIN * (1 + 0.01 * np.outer(np.sin(2 * np.pi * hz * t), PBV)) + rng.normal(0, noise, (len(t), 3))


def _one(ctx):
    results = pulse_coherence.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "pulse.coherence" and r.family == "A" and r.vote_group == "A.pulse" and r.window_id == "all"
    assert not r.flag and r.plot is None
    assert not [k for k in r.features if any(s in k.lower() for s in ("hr", "bpm", "wave", "rate", "freq"))]
    assert "not used in the decision" in r.explanation
    return r


def test_pos_finds_a_shared_pulse_and_tells_apart_another() -> None:
    rng = np.random.default_rng(0)
    neck = pos(_skin(1.2, 0.0006, rng), FS)
    snr, same = snr_and_coherence(pos(_skin(1.2, 0.0006, rng), FS), neck, FS)
    _, other = snr_and_coherence(pos(_skin(1.9, 0.0006, rng), FS), neck, FS)
    assert snr > 3 and same > 0.7 and other < 0.5


def test_a_shared_pulse_is_coherent_and_never_flags(synth) -> None:
    r = _one(synth.context(kind="genuine", pulse=0.05, seed=1))
    assert r.status == "usable" and r.risk == pytest.approx(1 - r.features["coherence_face_neck"])
    assert r.features["coherence_face_neck"] > 0.7 and r.features["seconds"] >= 10
    assert 0.5 < r.features["clean_share"] < 1  # the colour steps are left out


def test_a_face_with_its_own_pulse_is_less_coherent_but_still_never_flags(synth) -> None:
    same = _one(synth.context(kind="genuine", pulse=0.05, seed=1)).features["coherence_face_neck"]
    r = _one(synth.context(kind="genuine", pulse=0.05, face_pulse_hz=1.9, seed=1))
    assert r.status == "usable" and r.features["coherence_face_neck"] < same - 0.3 and r.risk > 0.5


def test_under_20_fps_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", pulse=0.05, fps=15.0))
    assert r.status == "abstain" and r.reason_codes == ["pulse.not_measured", "quality.low_fps"]


def test_a_short_session_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn=None, pulse=0.05))
    assert r.status == "abstain" and r.reason_codes == ["pulse.not_measured"] and r.features["seconds"] < 10


def test_no_face_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", face_in_frames=False))
    assert r.status == "abstain" and "pulse.not_measured" in r.reason_codes and "quality.no_face" in r.reason_codes


def test_identical_frames_abstain(synth) -> None:
    ctx = synth.context(kind="genuine", pulse=0.05, seed=1)
    for name in ("skin", "neck"):
        rgb = ctx.regions[name].rgb_linear
        rgb[:] = np.nanmean(rgb, axis=0)  # a still image: nothing changes frame to frame
    r = _one(ctx)
    assert r.status == "abstain" and r.reason_codes == ["pulse.not_measured"] and "identical" in r.explanation
