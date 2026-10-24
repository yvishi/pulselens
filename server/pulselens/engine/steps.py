"""One definition of the time window a challenge step occupies, in client ms since t0 (the FrameMeta.t_ms clock).

Painted..ended from the client event when the step was shown, else the schedule. Turn steps may add a tail.
"""

from __future__ import annotations

from dataclasses import dataclass

from pulselens.contracts import Challenge, ChallengeEvent, ColourStep, DigitStep, NodStep, TurnStep


@dataclass(frozen=True)
class StepWindow:
    step_id: str
    start_ms: float
    end_ms: float
    painted: bool  # True: from the client painted/ended event; False: from the schedule


def step_window(
    ch: Challenge, step: ColourStep | TurnStep | NodStep | DigitStep, event: ChallengeEvent | None, *,
    tail_ms: float = 0,
) -> StepWindow:
    is_turn = isinstance(step, TurnStep)
    length = step.dwell_ms if isinstance(step, ColourStep) else step.duration_ms
    tail = tail_ms if is_turn else 0
    if event is not None and event.status == "shown" and event.painted_t_ms is not None:
        end = event.ended_t_ms if event.ended_t_ms is not None else event.painted_t_ms + length
        return StepWindow(step.step_id, event.painted_t_ms, end + tail, True)
    start = ch.baseline_ms + step.start_offset_ms
    return StepWindow(step.step_id, start, start + length + tail, False)
