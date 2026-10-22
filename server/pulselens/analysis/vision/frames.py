"""Per-frame region means in linear light (the input to every optical check), and the frame hash for duplicates."""

from __future__ import annotations

import cv2
import numpy as np

from pulselens.analysis.vision.face import Box, FaceRegions

REGION_NAMES = ("skin", "left_cheek", "right_cheek", "neck", "background")
_NAN3 = np.full(3, np.nan)


def _box_sum(img: np.ndarray, box: Box) -> tuple[np.ndarray, int]:
    rows, cols = box.slices()
    patch = img[rows, cols].reshape(-1, 3)
    return patch.sum(axis=0), len(patch)


def _mean(img: np.ndarray, boxes: tuple[Box, ...]) -> np.ndarray:
    total, n = np.zeros(3), 0
    for b in boxes:
        s, k = _box_sum(img, b)
        total, n = total + s, n + k
    return total / n if n else _NAN3.copy()


def region_means(img: np.ndarray, regions: FaceRegions | None) -> dict[str, tuple[np.ndarray, float]]:
    """{region: (mean linear RGB, coverage 0..1)} of a linear RGB image. Without a face only the background (the
    whole frame) is measured."""
    if regions is None:
        empty = (_NAN3.copy(), 0.0)
        return {**{n: empty for n in REGION_NAMES[:-1]}, "background": (img.reshape(-1, 3).mean(axis=0), 1.0)}
    mask = np.ones(img.shape[:2], dtype=bool)
    for b in regions.background_exclude:
        rows, cols = b.clip(img.shape[1], img.shape[0]).slices()
        mask[rows, cols] = False
    background = img[mask].mean(axis=0) if mask.any() else _NAN3.copy()
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
