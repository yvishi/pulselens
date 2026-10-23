"""light.background (family C, C.relative, one vote with light.face_neck): the background answers the screen light
much less than the face. New in this repo; a hypothesis, measured, not assumed.

The face sits close to the screen and the room behind it is farther away, so a real face answers our light far
more than the wall. A flat replay screen filling the frame answers evenly (or not at all). Per colour step where the
face echo is clear, the ratio of the background's colour change to the face's, both projected on the colour shown
over the step (echo.response). Risk = 0.5 x median ratio / `max_bg_ratio` (0.8): flagged above 0.8.
Abstains when the background is mostly hidden or the face echo is weak (nothing to compare against).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.checks.light_common import colour_events, light_not_run, session_abstain
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.echo import echo_onset, response
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.linearize import srgb_to_linear
from pulselens.contracts import CheckResult

SPEC = specs.LIGHT_BACKGROUND
HYPOTHESIS = "This compares the face with the room behind it as a hypothesis against screen replays."


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    if light_not_run(ctx):
        return []
    ids = (SPEC.check_id, SPEC.family, SPEC.vote_group)
    if (gate := session_abstain(ctx, SPEC, "compare the face with the background")) is not None:
        return [gate]
    p = ctx.thresholds.params(SPEC.check_id)
    bg = ctx.regions["background"]
    face_seen = ctx.regions["skin"].coverage >= 0.5
    bg_cov = float(np.median(bg.coverage[face_seen])) if face_seen.any() else 0.0
    min_cov = float(p.get("min_coverage", 0.2))
    if bg_cov < min_cov:
        return [abstain(*ids, ["light.background_hidden"], f"Only {bg_cov:.0%} of the frame was background "
                        f"(need {min_cov:.0%}).", features={"background_coverage": bg_cov}, window_id="all")]

    a_min = float(ctx.thresholds.params("echo").get("a_min", 0.003))
    min_snr = float(ctx.thresholds.params("light.face_neck").get("min_snr", 2.0))
    events = colour_events(ctx)
    ratios, poor = [], 0
    for step, e in events:
        window = ctx.quality.windows.get(step.step_id)
        if window is not None and window.blocking():
            poor += 1
            continue
        colour = srgb_to_linear(np.asarray(e.shown_rgb, dtype=np.float64))
        ended = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.dwell_ms
        f = echo_onset(ctx.t, ctx.regions["skin"], e.painted_t_ms, ended, colour, a_min=a_min)
        if not (f.valid and f.amplitude and f.threshold and f.amplitude >= min_snr * f.threshold):
            continue
        rf = response(ctx.t, ctx.regions["skin"], e.painted_t_ms, ended, colour, a_min=a_min)
        rb = response(ctx.t, bg, e.painted_t_ms, ended, colour, a_min=a_min)
        if rf is None or rb is None or rf.cosine is None or rf.magnitude * rf.cosine <= 0:
            continue
        along_bg = rb.magnitude * rb.cosine if rb.cosine is not None else 0.0
        ratios.append(max(0.0, along_bg) / (rf.magnitude * rf.cosine))

    min_steps = int(p.get("min_steps", 3))
    features = {"steps": len(ratios), "median_bg_ratio": float(np.median(ratios)) if ratios else None,
                "background_coverage": bg_cov, "steps_poor_quality": poor}
    if len(ratios) < min_steps:
        return [abstain(*ids, ["light.weak_face_echo"], f"The face answered the light clearly on only {len(ratios)} "
                        f"of {len(events)} colour steps (need {min_steps}), so there is nothing to compare the "
                        "background with.", quality=len(ratios) / len(events), features=features, window_id="all")]
    ratio = features["median_bg_ratio"]
    max_ratio = float(p.get("max_bg_ratio", 0.8))
    risk = 0.5 * ratio / max_ratio
    flag_at = ctx.thresholds.flag_at(SPEC.check_id, 0.5)
    flagged = risk >= flag_at
    if flagged:
        explanation = (f"The background answered the screen light {ratio:.0%} as strongly as the face over "
                       f"{len(ratios)} steps (limit {max_ratio:.0%}), as a flat replay screen would. {HYPOTHESIS}")
    else:
        explanation = (f"The background answered the screen light {ratio:.0%} as strongly as the face over "
                       f"{len(ratios)} steps (limit {max_ratio:.0%}). {HYPOTHESIS}")
    return [result(*ids, risk=risk, flag_at=flag_at, quality=len(ratios) / len(events), features=features,
                   reasons=["light.background_even"] if flagged else [], explanation=explanation,
                   source=ctx.thresholds.source(SPEC.check_id), window_id="all",
                   voting=ctx.thresholds.voting(SPEC.check_id))]
