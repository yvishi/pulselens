"""sensor.regions (family B, B.regions): does the face carry the same sensor noise as the neck and the room around it?
New in this repo. **A hypothesis:** a face repainted by a live swap model may be smoother (or noisier) than the real
neck and background next to it, which one camera sensor gives about the same noise.

Per-frame temporal noise and sharpness of the face, neck and background come from build_context (vision/noise.py).
Only still frames count: the baseline and the gaps between steps, never a colour step (the light changes) or the
turn (the head moves), from 100 ms before a step to 400 ms after it.
- Scored: the median noise ratios face/neck and face/background. Risk grows from |ln ratio| beyond ln 2.5
  (`ratio_log_tolerance`), one unit per ln 2 (`ratio_log_scale`), from the worse of the two.
- Reported, not scored: the sharpness ratio face/neck (`sharp_face_neck_ratio`). Skin and a patterned shirt differ in
  texture for real, so it needs genuine data before it can mean anything.
Abstains when the face moves, the neck is hidden, a region is clipped, there are too few still frames, or the
video was compressed too hard to keep the sensor noise (JPEG quality under `min_jpeg_quality`, 80; G11: at quality
50 the encoder wiped the neck's noise to 0 and the ratio flagged a genuine face). The browser sends quality 90.
"""

from __future__ import annotations

import math

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, ColourStep, TurnStep

SPEC = specs.SENSOR_REGIONS
HYPOTHESIS = "A hypothesis: a repainted face may be smoother or noisier than the real neck."
BEFORE_STEP_MS, AFTER_STEP_MS = 100.0, 400.0
EPS = 1e-6  # two perfectly clean regions compare as equal, not as 0/0


def still_frames(ctx: AnalysisContext) -> np.ndarray:
    """Frames outside every shown step: no colour change, no requested head movement."""
    t = ctx.t
    keep = np.ones(ctx.n, dtype=bool)
    ch = ctx.bundle.challenge
    steps = {s.step_id: s for s in ch.steps} if ch is not None else {}
    for e in ctx.bundle.events:
        step = steps.get(e.step_id)
        if e.status != "shown" or e.painted_t_ms is None or step is None:
            continue
        if isinstance(step, ColourStep):
            end = (e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.dwell_ms) + AFTER_STEP_MS
        elif isinstance(step, TurnStep):
            tail = float(ctx.thresholds.param(specs.TURN_FOLLOW.check_id, "tail_ms"))
            end = (e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.duration_ms) + tail
        else:
            continue
        keep &= ~((t >= e.painted_t_ms - BEFORE_STEP_MS) & (t <= end))
    return keep


def _ratio(a: np.ndarray, b: np.ndarray, sel: np.ndarray) -> float | None:
    both = sel & np.isfinite(a) & np.isfinite(b)
    if not both.any():
        return None
    return float((np.median(a[both]) + EPS) / (np.median(b[both]) + EPS))


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    overall = ctx.quality.overall
    for code, what in (("quality.no_face", "the face was not visible enough"),
                       ("quality.moving", "the face moved too much"),
                       ("quality.neck_hidden", "the neck was not visible enough"),
                       ("quality.clipped", "parts of the picture were overexposed")):
        if code in overall.reasons:
            return [abstain(SPEC, [code], f"The noise of the face could not be compared: {what}.", window_id="all")]
    min_q = int(ctx.thresholds.param(SPEC.check_id, "min_jpeg_quality"))
    if ctx.jpeg_quality is not None and ctx.jpeg_quality < min_q:
        return [abstain(SPEC, ["quality.heavy_compression"], f"The video was compressed too heavily (JPEG quality "
                        f"about {ctx.jpeg_quality}, need {min_q}) to compare the sensor noise of the face and neck.",
                        features={"jpeg_quality": ctx.jpeg_quality}, window_id="all")]
    noise, sharp = ctx.noise, ctx.sharpness
    if not noise:
        return [abstain(SPEC, ["quality.too_few_frames"], "No region texture was measured.", window_id="all")]
    still = still_frames(ctx) & np.isfinite(noise["face"])
    min_frames = int(ctx.thresholds.param(SPEC.check_id, "min_frames"))
    n_still = int(still.sum())
    if n_still < min_frames:
        return [abstain(SPEC, ["quality.too_few_frames"], f"Only {n_still} still frames with a face (need "
                        f"{min_frames}) to compare the noise of the face, neck and background.",
                        features={"still_frames": n_still}, window_id="all")]

    face_neck = _ratio(noise["face"], noise["neck"], still)
    face_bg = _ratio(noise["face"], noise["background"], still)
    sharp_neck = _ratio(sharp["face"], sharp["neck"], still)
    features = {"noise_face_neck_ratio": face_neck, "noise_face_bg_ratio": face_bg,
                "sharp_face_neck_ratio": sharp_neck, "still_frames": n_still,
                "noise_face": float(np.nanmedian(noise["face"][still]))}
    scored = [r for r in (face_neck, face_bg) if r is not None and r > 0]
    if face_neck is None or not scored:
        return [abstain(SPEC, ["quality.neck_hidden"], "The neck's noise could not be measured on the still frames.",
                        features=features, window_id="all")]
    tol = float(ctx.thresholds.param(SPEC.check_id, "ratio_log_tolerance"))
    excess = max(abs(math.log(r)) for r in scored) - tol
    risk = max(0.0, excess) / float(ctx.thresholds.param(SPEC.check_id, "ratio_log_scale"))
    flag_at = ctx.thresholds.flag_at(SPEC.check_id)
    limit = math.exp(tol)
    bg = f" and {face_bg:.2f}x the background's" if face_bg is not None else ""
    explanation = (f"The face's sensor noise was {face_neck:.2f}x the neck's{bg} over {n_still} still frames "
                   f"(limit {limit:.1f}x either way). {HYPOTHESIS}")
    return [result(SPEC, ctx.thresholds, risk=risk, quality=min(1.0, n_still / (2 * min_frames)), features=features,
                   reasons=["sensor.regions_mismatch"] if risk >= flag_at else [], explanation=explanation,
                   window_id="all")]
