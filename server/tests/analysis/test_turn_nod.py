import numpy as np
import pytest

from pulselens.analysis.checks import turn_nod
from tests.analysis.conftest import requalify

GENUINE = {"kind": "genuine", "n_colour": 0, "turn": "left"}


def _one(ctx):
    results = turn_nod.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "turn.nod" and r.family == "D" and r.vote_group == "D.nod" and r.window_id == "n0"
    return r


def test_a_nod_performed_is_usable_and_not_flagged(synth) -> None:
    r = _one(synth.context(**GENUINE, nod="performed"))
    assert r.status == "usable" and not r.flag and r.risk == 0 and r.voting, r.explanation
    assert r.features["peak_deg"] == pytest.approx(20, abs=2)
    assert r.features["return_deg"] < 3 and r.features["face_present"] == 1
    assert 300 < r.features["latency_ms"] < 600  # 5 of 20 degrees into a ramp starting 300 ms after the prompt
    assert r.reason_codes == []
    assert r.plot is not None and len(r.plot.series["pitch"]) <= 300
    assert f"nodded {r.features['peak_deg']:.0f} degrees" in r.explanation


def test_a_nod_prompt_without_a_nod_abstains_never_flags(synth) -> None:
    r = _one(synth.context(**GENUINE, nod="skipped"))
    assert r.status == "abstain" and not r.flag and r.risk is None
    assert r.reason_codes == ["turn.nod_not_performed"]
    assert r.features["peak_deg"] < 3


def test_a_nod_prompt_never_shown_abstains(synth) -> None:
    r = _one(synth.context(**GENUINE, nod="not_shown"))
    assert r.status == "abstain" and r.reason_codes == ["turn.nod_not_performed"]
    assert "not shown" in r.explanation


def test_no_nod_step_is_not_run(synth) -> None:
    assert turn_nod.run(synth.context(**GENUINE)) == []


def test_the_sign_of_the_pitch_does_not_matter(synth) -> None:
    ctx = synth.context(**GENUINE, nod="performed")
    ctx.pitch = -ctx.pitch
    r = _one(ctx)
    assert r.status == "usable" and r.features["peak_deg"] == pytest.approx(20, abs=2)
    assert r.features["peak_neg_deg"] > r.features["peak_pos_deg"]


def test_no_face_in_the_nod_window_abstains_on_quality(synth) -> None:
    ctx = synth.context(**GENUINE, nod="performed")
    ev = next(e for e in ctx.bundle.events if e.step_id == "n0")
    gone = (ctx.t >= ev.painted_t_ms) & (ctx.t <= ev.ended_t_ms + 500)
    ctx.pitch[gone] = np.nan
    ctx.face_box[gone] = np.nan
    r = _one(requalify(ctx))
    assert r.status == "abstain" and "quality.no_face" in r.reason_codes and not r.flag


def test_a_head_still_away_at_the_end_is_noted_not_scored(synth) -> None:
    ctx = synth.context(**GENUINE, nod="performed")
    ev = next(e for e in ctx.bundle.events if e.step_id == "n0")
    ctx.pitch[ctx.t >= ev.painted_t_ms + 300] = 15.0
    r = _one(ctx)
    assert r.status == "usable" and r.risk == 0 and "turn.nod_no_return" in r.reason_codes
