"""visual.sbi (family D, D.detector): a benchmark-trained deepfake detector, used as one feature (vision/sbi.py).

Crops: 8 frames spread evenly over the session, from frames with a face, preferring still frames (no colour step
changing the face's colour, no head turn) that are near frontal (within 20 degrees of the session's median yaw), as
SBI was trained on mostly frontal FF++ video; falls back to any face frame when there are too few.
Risk = the mean of the top 3 crop scores (one bad stretch of a swap is enough to look at); `sbi_mean` is SBI's own
video score (the mean over frames), reported alongside. Provisional flag at 0.5 until G9 calibrates it.

Abstains when the weights are not installed (`visual.model_missing`) or with fewer than 4 face frames. The
detector was trained on FF++ benchmark video and may not transfer to Indian device streams: the explanation says so.
"""

from __future__ import annotations

import cv2
import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.checks.sensor_regions import still_frames
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision import sbi
from pulselens.contracts import CheckResult

SPEC = specs.VISUAL_SBI
CAVEAT = "A benchmark-trained detector (SBI, FF++) used as one feature; it may not transfer to Indian device streams."


def pick_frames(ctx: AnalysisContext, n: int, frontal_deg: float) -> np.ndarray:
    """Positions of up to `n` face frames spread evenly over the session: still and frontal first."""
    face = np.isfinite(ctx.face_box).all(axis=1) & (ctx.readable if len(ctx.readable) == ctx.n else True)
    yaw = ctx.yaw
    centre = float(np.nanmedian(yaw[face])) if np.isfinite(yaw[face]).any() else 0.0
    with np.errstate(invalid="ignore"):
        frontal = ~(np.abs(yaw - centre) > frontal_deg)  # NaN yaw counts as frontal
    for pool in (face & frontal & still_frames(ctx), face & frontal, face):
        idx = np.flatnonzero(pool)
        if len(idx) >= n:
            break
    if not len(idx):
        return idx
    return np.unique(idx[np.linspace(0, len(idx) - 1, min(n, len(idx))).round().astype(int)])


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    model = sbi.get_model()
    if model is None:
        return [abstain(SPEC, ["visual.model_missing"], "SBI weights not installed.", window_id="all")]
    p = ctx.thresholds.params(SPEC.check_id)
    n, min_crops, top_k = int(p.get("crops", 8)), int(p.get("min_crops", 4)), int(p.get("top_k", 3))
    crops = []
    for i in pick_frames(ctx, n, float(p.get("frontal_deg", 20))):
        img = ctx.bundle.read_frame(ctx.bundle.frames[i].idx)
        if img is not None:
            crops.append(sbi.crop(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), tuple(ctx.face_box[i])))
    if len(crops) < min_crops:
        return [abstain(SPEC, ["quality.no_face"], f"Only {len(crops)} frames with a face to show the detector "
                        f"(need {min_crops}).", features={"crops": len(crops)}, window_id="all")]
    scores = np.sort(model.score(crops))[::-1]
    top = float(np.mean(scores[:top_k]))
    flag_at = ctx.thresholds.flag_at(SPEC.check_id, 0.5)
    features = {"sbi_mean": float(np.mean(scores)), "sbi_top3": top, "sbi_max": float(scores[0]),
                "crops": len(crops)}
    explanation = (f"The detector scored the face {top:.2f} (mean of the top {min(top_k, len(scores))} of "
                   f"{len(crops)} frames; review level {flag_at:.2f}). {CAVEAT}")
    return [result(SPEC, ctx.thresholds, risk=top, quality=len(crops) / n, features=features,
                   reasons=["visual.sbi_high"] if top >= flag_at else [], explanation=explanation, window_id="all")]
