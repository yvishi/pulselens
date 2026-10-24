"""turn.identity (family D, D.identity): the face keeps its proportions through the head turn (G10).

A live face swap is rebuilt frame by frame; at large angles it can slip, and the face that comes back from the turn
need not have the proportions of the one that left. Before = the frames before the turn prompt; after = the frames
after the turn's peak, once the head is back. Both only at near-frontal yaw (within `frontal_deg` of the starting
angle), so the 2-D proportions are compared at the same pose. Proportions are vision/face.GEOMETRY_PAIRS: 10
distances between eye corners, nose, mouth corners and jaw, in units of the outer eye-corner distance; each side's
value is the median over its frames.

change = the median over the 10 distances of |after / before - 1| (the median, so one jittery landmark cannot decide);
risk = 0.5 x change / max_change, capped at 1, so it reaches flag_at 0.5 at the provisional 15% (`max_change`).

With the ArcFace model installed (vision/arcface.py, G10c), the decision is face recognition instead: up to
`arcface_frames` of the same before and after frames, spread evenly, are aligned on 5 landmarks and embedded; the
cosine similarity of the two mean embeddings (`arcface_similarity`) gives risk = 0.5 x (1 - similarity) /
(1 - min_similarity), so it reaches flag_at 0.5 at `min_similarity`. The proportions' `change` is still reported.
Without the model, or under `arcface_min_frames` embedded frames on a side, the proportions rule above decides.
Abstains with `turn.not_performed` when the head never turned (the largest yaw away from the start inside the turn
window stays under turn.follow's `min_peak_deg`: a still image is the same face before and after, which is no
evidence; S2, an OBS virtual camera still moved 0.002 degrees), `turn.face_lost` with no face in the window,
`turn.no_frontal` under `min_frames` frontal frames on either side, and on a session whose face was
missing, too dark or clipped (landmarks of a face that cannot be seen are not evidence).
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.landmarks import read_cache
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision import arcface
from pulselens.analysis.vision.face import to_pixels
from pulselens.contracts import CheckResult, TurnStep

SPEC = specs.TURN_IDENTITY
log = logging.getLogger("pulselens.analysis")
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
    window = np.isfinite(yaw) & (t >= painted) & (t <= ended)
    if not window.any():
        return [abstain(SPEC, ["turn.face_lost"], "The face was not seen during the turn, so there is no before and "
                        "after to compare.", window_id=step.step_id)]
    peak_deg = float(away[window].max())
    min_peak = float(ctx.thresholds.param(specs.TURN_FOLLOW.check_id, "min_peak_deg"))
    if peak_deg < min_peak:
        return [abstain(SPEC, ["turn.not_performed"], f"The head did not turn (at most {peak_deg:.1f} degrees, a turn "
                        f"is {min_peak:.0f}), so there is no before and after to compare.",
                        features={"peak_deg": peak_deg}, window_id=step.step_id)]
    in_turn = seen & window
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
    features = {"change": change, "max_pair_change": float(rel.max()), "frames_before": n_before,
                "frames_after": n_after}
    model = arcface.get_model()
    if model is not None:
        found = _arcface_similarity(ctx, model, before, after)
        if found is not None:
            sim, n_emb_before, n_emb_after = found
            features |= {"arcface_similarity": sim, "arcface_before": n_emb_before, "arcface_after": n_emb_after}
            return [_by_arcface(ctx, sim, change, features, step.step_id)]
    max_change = float(ctx.thresholds.param(SPEC.check_id, "max_change"))
    risk = min(1.0, 0.5 * change / max_change)
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


def _spread(mask: np.ndarray, n: int) -> np.ndarray:
    """Positions of up to `n` frames of `mask`, spread evenly over them."""
    idx = np.flatnonzero(mask)
    if len(idx) <= n:
        return idx
    return np.unique(idx[np.linspace(0, len(idx) - 1, n).round().astype(int)])


def _embed(ctx: AnalysisContext, model: arcface.ArcFaceModel, positions: np.ndarray,
           cache: dict[int, dict | None]) -> np.ndarray:
    """ArcFace embeddings of the frames at `positions` that decode and have all 5 alignment points."""
    crops = []
    for i in positions:
        idx = ctx.bundle.frames[i].idx
        found = cache.get(idx)
        img = ctx.bundle.read_frame(idx) if found and found.get("landmarks") else None
        if img is None:
            continue
        h, w = img.shape[:2]
        points = arcface.five_points(to_pixels(found["landmarks"], w, h))
        crop = None if points is None else arcface.align(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), points)
        if crop is not None:
            crops.append(crop)
    return model.embed(crops)


def _arcface_similarity(ctx: AnalysisContext, model: arcface.ArcFaceModel, before: np.ndarray,
                        after: np.ndarray) -> tuple[float, int, int] | None:
    """(cosine similarity of the mean embeddings, frames embedded before, after), or None (use the proportions)
    when the landmarks cache is missing or fewer than `arcface_min_frames` frames embed on either side."""
    cache = read_cache(ctx.bundle.path)
    if cache is None:
        return None
    n = int(ctx.thresholds.param(SPEC.check_id, "arcface_frames"))
    try:
        e0 = _embed(ctx, model, _spread(before, n), cache)
        e1 = _embed(ctx, model, _spread(after, n), cache)
    except Exception:  # noqa: BLE001 -- a failing model run leaves the proportions to decide, never a crash
        log.exception("ArcFace failed on %s; turn.identity uses the proportions", ctx.bundle.path)
        return None
    if min(len(e0), len(e1)) < int(ctx.thresholds.param(SPEC.check_id, "arcface_min_frames")):
        return None
    return arcface.similarity(e0, e1), len(e0), len(e1)


def _by_arcface(ctx: AnalysisContext, sim: float, change: float, features: dict, window_id: str) -> CheckResult:
    """risk = 0.5 x (1 - similarity) / (1 - min_similarity), clipped to 0..1: 0.5 (flag_at) at `min_similarity`."""
    min_sim = float(ctx.thresholds.param(SPEC.check_id, "min_similarity"))
    risk = min(1.0, max(0.0, 0.5 * (1 - sim) / (1 - min_sim)))
    if sim <= min_sim:
        reasons = ["turn.identity_mismatch"]
        explanation = (f"Face recognition matched the face after the turn to the one before it with similarity "
                       f"{sim:.2f}, below the {min_sim:.2f} the same person reaches (proportions changed by "
                       f"{change:.1%}).")
    else:
        reasons = []
        explanation = (f"Face recognition matched the face before and after the turn with similarity {sim:.2f} "
                       f"(review below {min_sim:.2f}; proportions changed by {change:.1%}), consistent with the same "
                       "person.")
    return result(SPEC, ctx.thresholds, risk=risk, quality=1.0, features=features, reasons=reasons,
                  explanation=explanation, window_id=window_id)
