"""Sensor fingerprint (PRNU) and PCE, for sensor.prnu. Ported from the old repo's vision/prnu.py; frames now go in one
at a time (`FingerprintAccumulator.add`), so build_context feeds it from its single decode pass.

1. Green channel of each usable frame (mean luma in LUMA_RANGE, native size), centre crop to at most CROP x CROP.
2. Residual W = I - D(I). D is a local adaptive Wiener denoiser in the pixel domain (keep the scene, leave the
   sensor's fine noise in W).
3. K = sum(W * I) / sum(I^2), separately on odd and even frames.
4. Zero-mean rows and columns, and the 8x8 block-phase means (the JPEG grid every encoder leaves, camera or not).
5. PCE between the two halves: the peak of the circular cross-correlation at zero shift, squared, over the mean
   square of the correlation outside a small window around it. A real sensor's pattern is white, so the peak is
   sharp; a static scene leaves smooth, wide correlation, so it cannot fake a high PCE.

Supporting evidence only: Chromium's fake camera produced a stable pattern (PCE 97) in the old repo, and compression
and browser scaling weaken a real one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import cv2
import numpy as np

CROP = 512
MIN_FRAMES = 30
LUMA_RANGE = (60, 200)  # mean 8-bit green of a usable fingerprint frame
PEAK_EXCLUDE = 5  # half-width of the window around the peak left out of the PCE denominator


@dataclass
class Fingerprint:
    pce: float
    frames: int  # usable frames
    skipped: int  # frames outside the luma range or of another size


def residual(gray: np.ndarray, size: int = 3) -> np.ndarray:
    """W = I - D(I), D a local Wiener filter with the noise level estimated as the median local variance."""
    mean = cv2.blur(gray, (size, size))
    var = np.maximum(cv2.blur(gray * gray, (size, size)) - mean * mean, 0.0)
    noise = float(np.median(var))
    gain = np.where(var > 0, np.maximum(var - noise, 0.0) / np.maximum(var, 1e-12), 0.0)
    return gray - (mean + gain * (gray - mean))


def _clean(k: np.ndarray) -> np.ndarray:
    k = k - k.mean(axis=1, keepdims=True)
    k = k - k.mean(axis=0, keepdims=True)
    h, w = k.shape
    for y in range(8):
        for x in range(8):
            k[y:h:8, x:w:8] -= k[y:h:8, x:w:8].mean()
    return k


def pce(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    corr = np.real(np.fft.ifft2(np.fft.fft2(a) * np.conj(np.fft.fft2(b))))
    peak = corr[0, 0]
    rolled = np.fft.fftshift(corr)
    cy, cx = rolled.shape[0] // 2, rolled.shape[1] // 2
    mask = np.ones_like(rolled, dtype=bool)
    mask[cy - PEAK_EXCLUDE : cy + PEAK_EXCLUDE + 1, cx - PEAK_EXCLUDE : cx + PEAK_EXCLUDE + 1] = False
    energy = float(np.mean(rolled[mask] ** 2))
    return float(np.sign(peak) * peak**2 / energy) if energy > 0 else 0.0


@dataclass
class FingerprintAccumulator:
    """Feed RGB uint8 frames in capture order with `add`; `result` is None below MIN_FRAMES usable frames."""

    used: int = 0
    skipped: int = 0
    _shape: tuple[int, int] | None = None
    _sums: list[list[np.ndarray]] = field(default_factory=list)  # [odd/even][numerator, denominator]

    def add(self, rgb: np.ndarray) -> None:
        g = np.asarray(rgb)[..., 1]
        if not LUMA_RANGE[0] <= float(g.mean()) <= LUMA_RANGE[1]:
            self.skipped += 1
            return
        h, w = g.shape
        ch, cw = min(CROP, h), min(CROP, w)
        g = g[(h - ch) // 2 : (h - ch) // 2 + ch, (w - cw) // 2 : (w - cw) // 2 + cw].astype(np.float64) / 255.0
        if self._shape is None:
            self._shape = g.shape
            self._sums = [[np.zeros(g.shape), np.zeros(g.shape)], [np.zeros(g.shape), np.zeros(g.shape)]]
        if g.shape != self._shape:
            self.skipped += 1
            return
        half = self._sums[self.used % 2]
        half[0] += residual(g) * g
        half[1] += g * g
        self.used += 1

    def result(self) -> Fingerprint | None:
        if self.used < MIN_FRAMES or self._shape is None:
            return None
        k = [_clean(num / np.maximum(den, 1e-12)) for num, den in self._sums]
        return Fingerprint(pce=pce(k[0], k[1]), frames=self.used, skipped=self.skipped)


def fingerprint(frames: Iterable[np.ndarray]) -> Fingerprint | None:
    """All frames at once (tests and tools): RGB uint8 frames in capture order."""
    acc = FingerprintAccumulator()
    for img in frames:
        acc.add(img)
    return acc.result()
