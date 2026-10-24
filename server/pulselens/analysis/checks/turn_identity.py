"""turn.identity (family D, D.identity): the face keeps its proportions through the head turn (G10).

A live face swap is rebuilt frame by frame; at large angles it can slip, and the face that comes back from the turn
need not have the proportions of the one that left. Before = the frames before the turn prompt; after = the frames
after the turn's peak, once the head is back. Both only at near-frontal yaw (within `frontal_deg` of the starting
angle), so the 2-D proportions are compared at the same pose. Proportions are vision/face.GEOMETRY_PAIRS: 10
distances between eye corners, nose, mouth corners and jaw, in units of the outer eye-corner distance; each side's
value is the median over its frames.

change = the median over the 10 distances of |after / before - 1| (the median, so one jittery landmark cannot decide);
risk = 0.5 x change / max_change, capped at 1, so it reaches flag_at 0.5 at the provisional 15% (`max_change`).
Abstains with `turn.no_frontal` under `min_frames` frontal frames on either side, and on a session whose face was
missing, too dark or clipped (landmarks of a face that cannot be seen are not evidence).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, TurnStep

SPEC = specs.TURN_IDENTITY
UNSEEN = ("quality.no_face", "quality.too_dark", "quality.clipped")


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    plan, ch = ctx.bundle.plan, ctx.bundle.challenge
    if (plan is not None and not plan.run_turn) or ch is None:
        return []
    step = next((s for s in ch.steps if isinstance(s, TurnStep)), None)
    if step is None:
        return []
    event = next((e for e in ctx.bundle.events if e.step_id == step.step_id), None)
    if event is None or event.status != "shown" or event.painted_t_ms is None:
        return [abstain(SPEC, ["turn.not_performed"], "The turn prompt was not shown, so there is no turn to compare "
                        "the face across.", window_id=step.step_id)]
    unseen = [r for r in UNSEEN if r in ctx.quality.overall.reasons]
    if unseen:
        why = " and ".join(reason_text(r).rstrip(".").lower() for r in unseen)
        return [abstain(SPEC, unseen, f"Unable to compare the face's proportions: {why}.", window_id="all")]

    painted = event.painted_t_ms
    ended = event.ended_t_ms if event.ended_t_ms is not None else painted + step.duration_ms
    t, yaw, geo = ctx.t, ctx.yaw, ctx.geometry
    seen = np.isfinite(yaw) & np.isfinite(geo).all(axis=1)
    pre = seen & (t < painted)
    if not pre.any():
        return [abstain(SPEC, ["turn.no_frontal"], "The face was not found before the turn prompt.",
                        window_id=step.step_id)]
    yaw0 = float(np.median(yaw[pre]))
    away = np.abs(yaw - yaw0)
    in_turn = seen & (t >= painted) & (t <= ended)
    t_peak = float(t[in_turn][np.argmax(away[in_turn])]) if in_turn.any() else ended
    frontal = away < float(ctx.thresholds.param(SPEC.check_id, "frontal_deg"))
    before, after = pre & frontal, seen & frontal & (t > t_peak)
    n_before, n_after = int(before.sum()), int(after.sum())
    min_frames = int(ctx.thresholds.param(SPEC.check_id, "min_frames"))
    if min(n_before, n_after) < min_frames:
        return [abstain(SPEC, ["turn.no_frontal"], f"Too few frontal frames to compare: {n_before} before the turn "
                        f"and {n_after} after it (need {min_frames} each).",
                        features={"frames_before": n_before, "frames_after": n_after}, window_id=step.step_id)]

    g0, g1 = np.median(geo[before], axis=0), np.median(geo[after], axis=0)
    rel = np.abs(g1 / g0 - 1)
    change = float(np.median(rel))
    max_change = float(ctx.thresholds.param(SPEC.check_id, "max_change"))
    risk = min(1.0, 0.5 * change / max_change)
    features = {"change": change, "max_pair_change": float(rel.max()), "frames_before": n_before,
                "frames_after": n_after}
    if change >= max_change:
        reasons = ["turn.identity_change"]
        explanation = (f"The face's proportions changed by {change:.0%} (median of 10 distances) between before and "
                       f"after the turn, more than the {max_change:.0%} a real face shows at the same pose.")
    else:
        reasons = []
        explanation = (f"The face's proportions changed by {change:.1%} through the turn (limit {max_change:.0%}), "
                       "consistent with the same face.")
    return [result(SPEC, ctx.thresholds, risk=risk, quality=1.0, features=features, reasons=reasons,
                   explanation=explanation, window_id=step.step_id)]
