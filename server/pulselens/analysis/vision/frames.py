"""Per-frame region means in linear light (the input to every optical check), and the frame hash for duplicates."""

from __future__ import annotations

import cv2
import numpy as np

from pulselens.analysis.vision.face import Box, FaceRegions
from pulselens.analysis.vision.linearize import srgb_to_linear

REGION_NAMES = ("skin", "left_cheek", "right_cheek", "neck", "background")
_NAN3 = np.full(3, np.nan)
_LUT = srgb_to_linear(np.arange(256, dtype=np.uint8))  # linear value of each 8-bit sRGB code
CLIP_CODE = 250  # an 8-bit pixel with any channel at or above this is blown out: it carries no colour change
MIN_UNCLIPPED = 0.2  # share of a region that must stay clean for its blown-out pixels to be left out
# The IJG standard luminance quantisation table (natural order), which browser and libjpeg encoders scale by quality.
_IJG_LUMA = np.array([
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99], dtype=np.float64)


def _linear_mean_u8(pixels: np.ndarray) -> np.ndarray:
    """Mean linear RGB of (k, 3) uint8 sRGB pixels: a histogram per channel dotted with the lookup table, the same
    value as linearising every pixel first, without building a float image. Blown-out pixels (any channel >=
    CLIP_CODE) are left out while at least MIN_UNCLIPPED of the region is clean (G11: a glare band on the forehead,
    57% of the skin sample, carries no echo and diluted the face's); a region blown out beyond that keeps every pixel,
    so the quality gate sees it clipped."""
    if len(pixels):
        keep = pixels.max(axis=1) < CLIP_CODE
        if not keep.all() and keep.mean() >= MIN_UNCLIPPED:
            pixels = pixels[keep]
    k = len(pixels)
    if not k:
        return _NAN3.copy()
    return np.array([np.bincount(pixels[:, c], minlength=256) @ _LUT for c in range(3)]) / k


def _pixels(img: np.ndarray, boxes: tuple[Box, ...]) -> np.ndarray:
    parts = [img[b.slices()].reshape(-1, 3) for b in boxes]
    return np.concatenate(parts) if parts else img[:0].reshape(-1, 3)


def _mean(img: np.ndarray, boxes: tuple[Box, ...]) -> np.ndarray:
    pixels = _pixels(img, boxes)
    if img.dtype == np.uint8:
        return _linear_mean_u8(pixels)
    return pixels.mean(axis=0) if len(pixels) else _NAN3.copy()


def _mean_all(pixels: np.ndarray) -> np.ndarray:
    if pixels.dtype == np.uint8:
        return _linear_mean_u8(pixels)
    return pixels.mean(axis=0) if len(pixels) else _NAN3.copy()


def region_means(img: np.ndarray, regions: FaceRegions | None) -> dict[str, tuple[np.ndarray, float]]:
    """{region: (mean linear RGB, coverage 0..1)}. `img` is either an RGB uint8 frame (sRGB codes, linearised through
    the lookup table) or a linear float image. Without a face only the background (the whole frame) is measured."""
    if regions is None:
        empty = (_NAN3.copy(), 0.0)
        return {**{n: empty for n in REGION_NAMES[:-1]}, "background": (_mean_all(img.reshape(-1, 3)), 1.0)}
    mask = np.ones(img.shape[:2], dtype=bool)
    for b in regions.background_exclude:
        rows, cols = b.clip(img.shape[1], img.shape[0]).slices()
        mask[rows, cols] = False
    background = _mean_all(img[mask]) if mask.any() else _NAN3.copy()
    neck_ok = regions.neck.area > 0
    return {
        "skin": (_mean(img, regions.skin), 1.0),
        "left_cheek": (_mean(img, (regions.left_cheek,)), 1.0),
        "right_cheek": (_mean(img, (regions.right_cheek,)), 1.0),
        "neck": (_mean(img, (regions.neck,)) if neck_ok else _NAN3.copy(), regions.neck_coverage if neck_ok else 0.0),
        "background": (background, float(mask.mean())),
    }


def jpeg_quality(data: bytes) -> int | None:
    """The encoder quality (1..100) of a JPEG, estimated from its luminance quantisation table against the IJG
    standard table the encoder scaled (libjpeg: scale = 5000 / q below 50, 200 - 2q above). None without a table."""
    i = data.find(b"\xff\xdb")
    while i >= 0 and i + 4 < len(data):
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        j, end = i + 4, i + 2 + length
        while j < end:
            precision, table_id = data[j] >> 4, data[j] & 0x0F
            size = 128 if precision else 64
            values = np.frombuffer(data[j + 1 : j + 1 + size], dtype=">u2" if precision else np.uint8)
            if table_id == 0 and len(values) == 64:
                scale = 100.0 * float(values.astype(np.float64).sum()) / float(_IJG_LUMA.sum())
                q = (200.0 - scale) / 2.0 if scale <= 100 else 5000.0 / scale
                return int(round(min(100.0, max(1.0, q))))
            j += 1 + size
        i = data.find(b"\xff\xdb", end)
    return None


def dhash(rgb: np.ndarray) -> int:
    """64-bit difference hash: 9x8 grey thumbnail, one bit per horizontal step."""
    grey = cv2.cvtColor(np.asarray(rgb, dtype=np.uint8), cv2.COLOR_RGB2GRAY)
    small = cv2.resize(grey, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).ravel()
    return int(sum(1 << k for k, b in enumerate(bits) if b))
