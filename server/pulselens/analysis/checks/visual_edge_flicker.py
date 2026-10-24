"""visual.edge_flicker (family D, D.edge): does the edge of the face change more from frame to frame than its middle?
New in this repo (G12). **A hypothesis:** a live face swap (Deep-Live-Cam and the like) blends a generated face into
the real video; the blend boundary near the face contour flickers from frame to frame, while real skin at the edge of
the face changes no more than the cheeks and forehead.

Per pair of consecutive still frames (sensor_regions.still_frames: no colour step, no turn), both with a face, the
frame-to-frame difference of linear green, and its robust spread (vision/noise.robust_sigma: the pixels that moved
are trimmed) in two regions of the later frame:
- the edge: a ring just inside the face contour, between the ellipse inscribed in the landmark face box scaled to
  `ring_inner` and to `ring_outer` (0.85 to 1.0); inside the contour, so hair and background stay out;
- the inner face: the forehead and cheek boxes (vision/face.FaceRegions.skin).
The context keeps no pixels, so the check reads its own frames: every `stride`-th pair, at most `max_pairs`, only the
face box of each. edge_inner_ratio = the median over pairs of edge / inner. Risk = (ratio - `ratio_tolerance`) /
`ratio_scale`: 0 up to 1.5, 0.5 at 2.0. Only the high side counts: an edge calmer than the middle is not evidence.

Measured, not voting (`voting: false`), until real swaps and 20+ genuine sessions calibrate it. G12, 15 real genuine
webcam sessions: 0.73-1.16 (risk 0); a YouTube video replayed to the webcam: 2.87 (not a swap, so this says nothing
about the hypothesis yet). Abstains when the face was missing, too dark, clipped or moving (the "all" window), the
video was compressed too hard to keep the sensor noise (smooth skin loses it first, which would raise the ratio), or
there are under `min_pairs` usable pairs.
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.checks.sensor_regions import still_frames
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.landmarks import read_cache
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.face import Box, regions_from_landmarks, to_pixels
from pulselens.analysis.vision.noise import GREEN_LUT, MIN_PIXELS, robust_sigma
from pulselens.contracts import CheckResult

SPEC = specs.VISUAL_EDGE_FLICKER
HYPOTHESIS = "A hypothesis: the blend boundary of a live face swap flickers; real skin at the face's edge does not."
UNSEEN = ("quality.no_face", "quality.too_dark", "quality.clipped", "quality.moving")
EPS = 1e-6  # two perfectly clean regions compare as equal, not as 0/0


def _pairs(ctx: AnalysisContext, stride: int, cap: int) -> np.ndarray:
    """Positions i whose frame and the one before are both readable, still and with a face; every `stride`-th."""
    ok = np.isfinite(ctx.face_box).all(axis=1) & still_frames(ctx)
    if len(ctx.readable) == ctx.n:
        ok &= ctx.readable
    both = np.flatnonzero(ok[1:] & ok[:-1]) + 1
    return both[::stride][:cap]


def _ring(box: Box, crop: Box, inner: float, outer: float) -> np.ndarray:
    """Mask (crop-sized) of the ring between the box's inscribed ellipse scaled to `inner` and to `outer`."""
    rows, cols = crop.slices()
    yy, xx = np.mgrid[rows, cols]
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    ax, ay = max((box.x1 - box.x0) / 2, 1.0), max((box.y1 - box.y0) / 2, 1.0)
    r2 = ((xx + 0.5 - cx) / ax) ** 2 + ((yy + 0.5 - cy) / ay) ** 2
    return (r2 >= inner * inner) & (r2 < outer * outer)


def _spreads(ctx: AnalysisContext, lms: dict, i: int, inner: float, outer: float) -> tuple[float, float] | None:
    """(edge, inner face) spread of the green difference between frame i - 1 and frame i, or None."""
    found = lms.get(ctx.bundle.frames[i].idx)
    if not found or not found.get("landmarks"):
        return None
    cur = ctx.bundle.read_frame(ctx.bundle.frames[i].idx)
    prev = ctx.bundle.read_frame(ctx.bundle.frames[i - 1].idx)
    if cur is None or prev is None or cur.shape != prev.shape:
        return None
    h, w = cur.shape[:2]
    regions = regions_from_landmarks(to_pixels(found["landmarks"], w, h), w, h)
    crop = regions.face_box.clip(w, h)
    rows, cols = crop.slices()
    # Channel 1 is green in BGR as in RGB.
    diff = GREEN_LUT[cur[rows, cols, 1]] - GREEN_LUT[prev[rows, cols, 1]]
    if diff.size == 0:
        return None
    ring = _ring(regions.face_box, crop, inner, outer)
    skin = np.zeros(diff.shape, dtype=bool)
    for b in regions.skin:  # inside the face box; clipped to the crop all the same
        r, c = b.clip(w, h).slices()
        skin[max(r.start - rows.start, 0):max(r.stop - rows.start, 0),
             max(c.start - cols.start, 0):max(c.stop - cols.start, 0)] = True
    skin &= ~ring
    if ring.sum() < MIN_PIXELS or skin.sum() < MIN_PIXELS:
        return None
    return robust_sigma(diff[ring]), robust_sigma(diff[skin])


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    unseen = [r for r in UNSEEN if r in ctx.quality.overall.reasons]
    if unseen:
        why = " and ".join(reason_text(r).rstrip(".").lower() for r in unseen)
        return [abstain(SPEC, unseen, f"Unable to compare the edge of the face with its middle: {why}.",
                        window_id="all")]
    param = ctx.thresholds.param
    min_q = int(param(SPEC.check_id, "min_jpeg_quality"))
    if ctx.jpeg_quality is not None and ctx.jpeg_quality < min_q:
        return [abstain(SPEC, ["quality.heavy_compression"], f"The video was compressed too heavily (JPEG quality "
                        f"about {ctx.jpeg_quality}, need {min_q}) to compare frame-to-frame change at the face's "
                        "edge and in its middle.", features={"jpeg_quality": ctx.jpeg_quality}, window_id="all")]
    min_pairs = int(param(SPEC.check_id, "min_pairs"))
    inner, outer = float(param(SPEC.check_id, "ring_inner")), float(param(SPEC.check_id, "ring_outer"))
    lms = read_cache(ctx.bundle.path) or {}
    edge, middle = [], []
    for i in _pairs(ctx, int(param(SPEC.check_id, "stride")), int(param(SPEC.check_id, "max_pairs"))):
        s = _spreads(ctx, lms, int(i), inner, outer)
        if s is not None and np.isfinite(s).all():
            edge.append(s[0])
            middle.append(s[1])
    n = len(edge)
    if n < min_pairs:
        return [abstain(SPEC, ["quality.too_few_frames"], f"Only {n} pairs of still frames with a face (need "
                        f"{min_pairs}) to compare the edge of the face with its middle.", features={"frames": n},
                        window_id="all")]

    e, m = np.asarray(edge), np.asarray(middle)
    ratio = float(np.median((e + EPS) / (m + EPS)))
    tol = float(param(SPEC.check_id, "ratio_tolerance"))
    risk = max(0.0, ratio - tol) / float(param(SPEC.check_id, "ratio_scale"))
    flag_at = ctx.thresholds.flag_at(SPEC.check_id)
    features = {"edge_inner_ratio": ratio, "frames": n, "edge_noise": float(np.median(e)),
                "inner_noise": float(np.median(m))}
    explanation = (f"The edge of the face changed {ratio:.2f}x as much as its middle from frame to frame, over {n} "
                   f"pairs of still frames (up to {tol:.1f}x scores nothing). {HYPOTHESIS}")
    return [result(SPEC, ctx.thresholds, risk=risk, quality=min(1.0, n / (2 * min_pairs)), features=features,
                   reasons=["visual.edge_flicker_high"] if risk >= flag_at else [], explanation=explanation,
                   window_id="all")]
