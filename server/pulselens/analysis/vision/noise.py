"""Per-region texture of one frame, for sensor.regions: temporal noise and sharpness of the face, neck and background.
New in this repo (the old repo's noise curve was one number for the whole frame). Pure: frames in, numbers out.

- noise: the frame-to-frame difference of linear green inside the region. Its robust spread (around its median, so a
  uniform brightness change does not count, without the 5% furthest out, so the few pixels that moved do not
  either) / sqrt(2) is the sensor noise of one frame. A real camera gives the face, the neck and the wall about the
  same noise; a face repainted by a swap model may be smoother (or noisier) than the real neck around it.
- sharpness: variance of the Laplacian of the 8-bit green channel inside the region.
"""

from __future__ import annotations

import cv2
import numpy as np

from pulselens.analysis.vision.face import Box, FaceRegions
from pulselens.analysis.vision.linearize import srgb_to_linear

TEXTURE_REGIONS = ("face", "neck", "background")
MIN_PIXELS = 200
BACKGROUND_STRIDE = 2  # every 2nd row and column of the background: it is most of the frame
GREEN_LUT = srgb_to_linear(np.arange(256, dtype=np.uint8)).astype(np.float32)


def linear_green(rgb: np.ndarray) -> np.ndarray:
    """Linear green of an RGB uint8 frame, float32 (the input `region_texture` diffs between frames)."""
    return GREEN_LUT[np.asarray(rgb)[..., 1]]


def _boxes(img: np.ndarray, boxes: tuple[Box, ...]) -> np.ndarray:
    h, w = img.shape[:2]
    parts = [img[b.clip(w, h).slices()].ravel() for b in boxes]
    return np.concatenate(parts) if parts else img[:0, :0].ravel()


def _background(img: np.ndarray, regions: FaceRegions) -> np.ndarray:
    h, w = img.shape[:2]
    mask = np.ones((h, w), dtype=bool)
    for b in regions.background_exclude:
        mask[b.clip(w, h).slices()] = False
    s = BACKGROUND_STRIDE
    return img[::s, ::s][mask[::s, ::s]]


def _pixels(img: np.ndarray, regions: FaceRegions) -> dict[str, np.ndarray]:
    return {"face": _boxes(img, regions.skin), "neck": _boxes(img, (regions.neck,)) if regions.neck.area > 0
            else img[:0, :0].ravel(), "background": _background(img, regions)}


TRIM = 0.95  # share of the differences kept, the closest to their median
TRIM_FACTOR = 0.871  # the spread of the central 95% of a Gaussian, in sigmas


def robust_sigma(x: np.ndarray) -> float:
    """The spread of `x` around its median from the central 95% (the pixels that moved are in the tails). A trimmed
    RMS, not the MAD: frame differences of an 8-bit camera are integer codes, and the MAD of a spread under a few
    codes snaps to the code steps."""
    y = x - np.median(x)
    a = np.abs(y)
    kept = y[a <= np.quantile(a, TRIM)]
    return float(np.sqrt(np.mean(kept * kept)) / TRIM_FACTOR) if len(kept) else float("nan")


def region_texture(rgb: np.ndarray, green: np.ndarray, prev_green: np.ndarray | None,
                   regions: FaceRegions | None) -> dict[str, tuple[float, float]]:
    """{region: (noise, sharpness)}, NaN where it cannot be measured (no face, too few pixels, no previous frame of
    the same size). `green` is `linear_green(rgb)`; `prev_green` the previous readable frame's."""
    nan = {name: (np.nan, np.nan) for name in TEXTURE_REGIONS}
    if regions is None:
        return nan
    lap = cv2.Laplacian(np.asarray(rgb)[..., 1], cv2.CV_32F)
    diff = green - prev_green if prev_green is not None and prev_green.shape == green.shape else None
    sharp = _pixels(lap, regions)
    moved = _pixels(diff, regions) if diff is not None else {}
    out = {}
    for name in TEXTURE_REGIONS:
        s = sharp[name]
        d = moved.get(name)
        out[name] = (
            robust_sigma(d) / np.sqrt(2) if d is not None and len(d) >= MIN_PIXELS else np.nan,
            float(np.var(s)) if len(s) >= MIN_PIXELS else np.nan,
        )
    return out
