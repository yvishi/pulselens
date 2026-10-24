"""light.face_neck (family C, C.relative): does the face answer the screen light the way the neck (or shirt) does?
Ported from the old optical.face_neck check. A hypothesis against live face swaps, measured, not assumed.

The screen light reaches the face and the neck together. A swap redraws only the face, so its echo is missing or far
weaker than the neck's. Per colour step, echo onsets and amplitudes for the face (skin) and the neck:
- a pair: both echoes clear (hold amplitude >= `min_snr` x their own threshold): amplitude ratio face/neck, and the
  constant-fraction delay face - neck (reported only: one webcam frame, 64-96 ms, is longer than any lag limit);
- neck only: the neck's echo is clear and the face is *clearly* silent. Silent needs a face threshold low enough to
  hear an eighth of the neck's echo (the weakest real face/neck ratio, exp(-ratio_log_tolerance)); otherwise the step
  is unclear and counts for neither side (the old repo's fix, after a darker exposure-locked face was misread). A face
  whose mean change over the step still pushes towards the colour shown (`echo.faint_z` standard errors, echo.hold_z)
  answered faintly, under weak light, and is unclear too (issue #17).
Risk 1 when at least `neck_only_steps` (2) steps are neck only and they are at least half of the measured steps
(kept from the old repo, so one odd step cannot flag a genuine person). Otherwise risk grows from |ln median ratio|
beyond ln 8 (S2: real faces answered down to 1/6.3 of a shirt).
Abstains when the neck is hidden or clipped, or with fewer than `min_pairs` (3) pairs.
"""

from __future__ import annotations

import math

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.checks.light_common import colour_events, light_not_run, session_abstain
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.echo import EchoOnset, echo_onset
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.linearize import srgb_to_linear
from pulselens.contracts import CheckResult

SPEC = specs.LIGHT_FACE_NECK
HYPOTHESIS = "This compares the face with the neck as a hypothesis against live face swaps."


def _clear(o: EchoOnset, min_snr: float) -> bool:
    """An echo strong enough to compare: its hold amplitude reaches `min_snr` times its own detection threshold."""
    return bool(o.amplitude and o.threshold and o.amplitude >= min_snr * o.threshold)


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    if light_not_run(ctx):
        return []
    if (gate := session_abstain(ctx, SPEC, "compare the face with the neck")) is not None:
        return [gate]
    overall = ctx.quality.overall
    if "quality.neck_hidden" in overall.reasons:
        return [abstain(SPEC, ["quality.neck_hidden"], f"Only {overall.neck_coverage:.0%} of the neck area was in "
                        "the frame, too little to compare with the face.",
                        features={"neck_coverage": overall.neck_coverage}, window_id="all")]
    sat = float(ctx.thresholds.param("quality", "saturation"))
    face_seen = ctx.regions["skin"].coverage >= 0.5
    neck = ctx.regions["neck"]
    with np.errstate(invalid="ignore"):
        neck_level = float(np.nanmedian(neck.rgb_linear[face_seen].max(axis=1))) if face_seen.any() else math.nan
    if not math.isfinite(neck_level) or neck_level > sat:
        return [abstain(SPEC, ["quality.clipped"], "The neck was too bright to see a colour change.",
                        features={"neck_level": neck_level}, window_id="all")]

    a_min = float(ctx.thresholds.param("echo", "a_min"))
    min_snr = float(ctx.thresholds.param(SPEC.check_id, "min_snr"))
    tol = float(ctx.thresholds.param(SPEC.check_id, "ratio_log_tolerance"))
    ratio_floor = math.exp(-tol)  # the weakest face/neck ratio a real face shows
    faint_z = float(ctx.thresholds.param("echo", "faint_z"))
    ratios, deltas = [], []
    neck_only = face_only = weak = unclear = poor = measured = 0
    events = colour_events(ctx)
    for step, e in events:
        window = ctx.quality.windows.get(step.step_id)
        if window is not None and window.blocking(neck=True):
            poor += 1
            continue
        colour = srgb_to_linear(np.asarray(e.shown_rgb, dtype=np.float64))
        ended = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.dwell_ms
        f = echo_onset(ctx.t, ctx.regions["skin"], e.painted_t_ms, ended, colour, step_id=step.step_id,
                       region="skin", a_min=a_min)
        n = echo_onset(ctx.t, neck, e.painted_t_ms, ended, colour, step_id=step.step_id, region="neck", a_min=a_min)
        if not (f.valid and n.valid):
            continue
        if f.onset_cf_ms is not None and n.onset_cf_ms is not None:
            measured += 1  # the face answered, even if too weakly to compare
            if not (_clear(f, min_snr) and _clear(n, min_snr)):
                weak += 1
                continue
            ratios.append(f.amplitude / n.amplitude)
            deltas.append(f.onset_cf_ms - n.onset_cf_ms)
        elif n.onset_ms is not None and _clear(n, min_snr):
            audible = (f.threshold or 0.0) <= ratio_floor * (n.amplitude or 0.0)
            faint = f.hold_z is not None and f.hold_z >= faint_z
            if audible and not faint and (f.peak is None or f.peak < (f.threshold or 0.0)):
                measured += 1
                neck_only += 1
            else:
                unclear += 1
        elif f.onset_ms is not None and n.onset_ms is None:
            face_only += 1

    features = {
        "pairs": len(ratios),
        "median_ratio": float(np.median(ratios)) if ratios else None,
        "neck_only_steps": neck_only,
        "face_only_steps": face_only,
        "weak_steps": weak,
        "unclear_steps": unclear,
        "steps_poor_quality": poor,
        "median_cf_delta_ms": float(np.median(deltas)) if deltas else None,  # informative only, not scored
        "neck_coverage": overall.neck_coverage,
    }
    quality = measured / len(events)
    flag_at = ctx.thresholds.flag_at(SPEC.check_id)
    if neck_only >= int(ctx.thresholds.param(SPEC.check_id, "neck_only_steps")) and neck_only * 2 >= measured:
        return [result(SPEC, ctx.thresholds, risk=1.0, quality=quality, features=features,
                       reasons=["light.neck_only"], window_id="all",
                       explanation=f"The neck answered the screen light on {neck_only} of {measured} colour steps "
                                   f"while the face did not, as a face drawn over a real person would. {HYPOTHESIS}")]
    min_pairs = int(ctx.thresholds.param(SPEC.check_id, "min_pairs"))
    if len(ratios) < min_pairs:
        detail = "; ".join(x for x in (f"{weak} too close to the noise" if weak else "",
                                       f"{unclear} too noisy on the face to tell" if unclear else "",
                                       f"{poor} with poor capture" if poor else "") if x)
        return [abstain(SPEC, ["light.too_few_steps"] + ["light.weak_echoes"] * (weak + unclear > 0),
                        f"Face and neck both answered clearly on {len(ratios)} of {len(events)} colour steps "
                        f"(need {min_pairs}){'; ' + detail if detail else ''}.", quality=quality, features=features,
                        window_id="all")]

    ratio = features["median_ratio"]
    excess = max(0.0, abs(math.log(ratio)) - tol)
    risk = excess / float(ctx.thresholds.param(SPEC.check_id, "ratio_log_scale"))
    flagged = risk >= flag_at
    if flagged:
        explanation = (f"The face answered the light {ratio:.2f}x as strongly as the neck over {len(ratios)} steps, "
                       f"outside the {1 / ratio_floor:.0f}x either way a real face shows. {HYPOTHESIS}")
    else:
        explanation = (f"The face and neck answered the light together on {len(ratios)} colour steps "
                       f"(face/neck {ratio:.2f}x, within {1 / ratio_floor:.0f}x either way). {HYPOTHESIS}")
    return [result(SPEC, ctx.thresholds, risk=risk, quality=quality, features=features,
                   reasons=["light.ratio"] if flagged else [], explanation=explanation,
                   window_id="all")]
