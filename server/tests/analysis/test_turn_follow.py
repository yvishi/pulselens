import numpy as np
import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks import turn_follow


def _one(ctx):
    results = turn_follow.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "turn.follow" and r.family == "D" and r.vote_group == "D.turn" and r.window_id == "t0"
    return r


@pytest.mark.parametrize("direction", ["left", "right"])
def test_a_turn_followed_and_returned_is_not_flagged(synth, direction: str) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn=direction))
    assert r.status == "usable" and not r.flag and r.risk == 0, r.explanation
    assert r.features["peak_deg"] == pytest.approx(30, abs=2)
    assert r.features["wrong_peak_deg"] < 3 and r.features["return_deg"] < 3
    assert r.features["latency_ms"] == pytest.approx(300 + 400 / 3, abs=15)  # 10 of 30 degrees into the ramp
    assert r.features["face_present"] == 1
    assert r.reason_codes == []
    assert r.plot is not None and r.plot.kind == "turn" and len(r.plot.series["yaw"]) <= 300
    assert [label for _, label in r.plot.markers] == ["painted", "ended"]
    assert f"{r.features['peak_deg']:.0f} degrees" in r.explanation


def test_right_requested_but_left_performed_is_flagged(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="right", turn_performed="left"))
    assert r.flag and r.risk == 1.0 and "turn.wrong_direction" in r.reason_codes
    assert r.features["wrong_peak_deg"] >= 15 and r.features["peak_deg"] < 10


def test_no_movement_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", turn_followed=False))
    assert r.status == "abstain" and not r.flag and r.risk is None
    assert "turn.not_performed" in r.reason_codes


def test_no_turn_step_is_not_run(synth) -> None:
    assert turn_follow.run(synth.context(kind="genuine", turn=None)) == []


def test_a_face_lost_for_most_of_the_turn_is_a_hypothesis_flag(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", face_lost_in_turn=0.6))
    assert r.status == "usable" and r.risk == pytest.approx(0.6) and r.flag
    assert "turn.face_lost" in r.reason_codes and r.features["face_present"] < 0.6
    assert "hypothesis" in r.explanation


def test_a_short_face_loss_is_fine(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", face_lost_in_turn=0.2))
    assert r.status == "usable" and not r.flag


def test_turned_but_did_not_return_is_not_flagged(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", turn_returns=False))
    assert r.status == "usable" and not r.flag and "turn.no_return" in r.reason_codes
    assert r.features["return_deg"] > 10


def test_a_very_fast_start_is_noted_but_not_scored(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=0, turn="left", turn_start_ms=0))  # 10 degrees at ~133 ms
    assert r.status == "usable" and not r.flag and r.risk == 0
    assert "turn.too_fast" in r.reason_codes and r.features["latency_ms"] < 150


def test_no_face_before_the_prompt_abstains(synth) -> None:
    ctx = synth.context(kind="genuine", n_colour=0, turn="left")
    ev = next(e for e in ctx.bundle.events if e.step_id == "t0")
    ctx.yaw[ctx.t < ev.painted_t_ms] = np.nan
    r = _one(ctx)
    assert r.status == "abstain" and "quality.no_face" in r.reason_codes


def test_the_turn_window_ignores_the_light_steps(synth) -> None:
    # A full session (light, then the turn): the colour steps do not disturb the yaw baseline.
    r = _one(synth.context(kind="genuine"))
    assert r.status == "usable" and not r.flag


def test_analyze_includes_turn_follow(synth) -> None:
    ids = {r.check_id for r in analyze(synth.session(kind="genuine"))}
    assert "turn.follow" in ids
