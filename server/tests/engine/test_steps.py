from __future__ import annotations

from pulselens.contracts import Challenge, ChallengeEvent, ColourStep, TurnStep
from pulselens.engine.steps import StepWindow, step_window

COLOUR = ColourStep(step_id="c0", hue_deg=120, start_offset_ms=1000, dwell_ms=400)
TURN = TurnStep(step_id="t0", direction="left", start_offset_ms=3000, duration_ms=2000)
CH = Challenge(session_id="s", nonce="n", mode="CAPABLE", baseline_ms=500, steps=[COLOUR, TURN], total_ms=6000)


def _event(step_id: str, painted: float | None, ended: float | None, status: str = "shown") -> ChallengeEvent:
    return ChallengeEvent(step_id=step_id, status=status, painted_t_ms=painted, ended_t_ms=ended, shown_rgb=None)


def test_painted_colour_uses_event_span():
    w = step_window(CH, COLOUR, _event("c0", 1530.0, 1950.0))
    assert w == StepWindow("c0", 1530.0, 1950.0, True)


def test_painted_colour_without_end_falls_back_to_dwell():
    w = step_window(CH, COLOUR, _event("c0", 1530.0, None))
    assert w == StepWindow("c0", 1530.0, 1930.0, True)


def test_unpainted_colour_uses_schedule():
    expected = StepWindow("c0", 1500, 1900, False)
    assert step_window(CH, COLOUR, None) == expected
    assert step_window(CH, COLOUR, _event("c0", None, None, status="skipped")) == expected


def test_tail_applies_to_turn_only():
    assert step_window(CH, TURN, None, tail_ms=500) == StepWindow("t0", 3500, 6000, False)
    assert step_window(CH, TURN, _event("t0", 3600.0, 5500.0), tail_ms=500) == StepWindow("t0", 3600.0, 6000.0, True)
    assert step_window(CH, COLOUR, None, tail_ms=500) == StepWindow("c0", 1500, 1900, False)
