"""Per-frame region means in linear light (the input to every optical check), and the frame hash for duplicates."""

from __future__ import annotations

import cv2
import numpy as np

from pulselens.analysis.vision.face import Box, FaceRegions
from pulselens.analysis.vision.linearize import srgb_to_linear

REGION_NAMES = ("skin", "left_cheek", "right_cheek", "neck", "background")
_NAN3 = np.full(3, np.nan)
_LUT = srgb_to_linear(np.arange(256, dtype=np.uint8))  # linear value of each 8-bit sRGB code


def _linear_mean_u8(pixels: np.ndarray) -> np.ndarray:
    """Mean linear RGB of (k, 3) uint8 sRGB pixels: a histogram per channel dotted with the lookup table, the same
    value as linearising every pixel first, without building a float image."""
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


def dhash(rgb: np.ndarray) -> int:
    """64-bit difference hash: 9x8 grey thumbnail, one bit per horizontal step."""
    grey = cv2.cvtColor(np.asarray(rgb, dtype=np.uint8), cv2.COLOR_RGB2GRAY)
    small = cv2.resize(grey, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).ravel()
    return int(sum(1 << k for k, b in enumerate(bits) if b))
