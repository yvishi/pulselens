"""What the family C light checks share: the shown colour steps, and the session-level abstains."""

from __future__ import annotations

from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import CheckSpec, abstain
from pulselens.contracts import ChallengeEvent, CheckResult, ColourStep


def colour_events(ctx: AnalysisContext) -> list[tuple[ColourStep, ChallengeEvent]]:
    """Colour steps the client reports as shown, with a painted time and colour, in step order."""
    ch = ctx.bundle.challenge
    if ch is None:
        return []
    shown = {e.step_id: e for e in ctx.bundle.events
             if e.status == "shown" and e.painted_t_ms is not None and e.shown_rgb is not None}
    return [(s, shown[s.step_id]) for s in ch.steps if isinstance(s, ColourStep) and s.step_id in shown]


def light_not_run(ctx: AnalysisContext) -> bool:
    """No result at all (family state not_run): the plan has no light, or no colour step was shown."""
    plan = ctx.bundle.plan
    return (plan is not None and not plan.run_light) or not colour_events(ctx)


def session_abstain(ctx: AnalysisContext, spec: CheckSpec, what: str) -> CheckResult | None:
    """An abstain when the whole session is below the fps floor or the face is missing; else None."""
    overall = ctx.quality.overall
    if "quality.low_fps" in overall.reasons:
        min_fps = float(ctx.thresholds.param("quality", "min_fps"))
        return abstain(spec, overall.blocking(), f"The camera delivered {overall.fps:.1f} fps, below the "
                       f"{min_fps:.0f} fps needed to {what}.", features={"fps": overall.fps}, window_id="all")
    if "quality.no_face" in overall.reasons:
        min_present = float(ctx.thresholds.param("quality", "min_face_present"))
        return abstain(spec, overall.blocking(), f"The face was visible in {overall.face_present:.0%} of frames "
                       f"(need {min_present:.0%}).", quality=overall.face_present,
                       features={"face_present": overall.face_present}, window_id="all")
    return None
