import numpy as np
import pytest

from pulselens.analysis.checks import turn_identity
from pulselens.analysis.vision.face import GEOMETRY_PAIRS, face_geometry
from tests.fixtures.synth import synthetic_landmarks


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


def test_no_face_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", face_in_frames=False))
    assert r.status == "abstain" and not r.flag and "quality.no_face" in r.reason_codes


def test_no_turn_step_is_not_run(synth) -> None:
    assert turn_identity.run(synth.context(kind="genuine", turn=None)) == []
