"""sRGB transfer functions (IEC 61966-2-1). All colour and noise maths runs in linear light (ported as is)."""

from __future__ import annotations

import numpy as np


def _decode(a: np.ndarray) -> np.ndarray:
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


_LUT = _decode(np.arange(256) / 255.0)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """Encoded sRGB to linear light. uint8 input is read as 0-255 (via a lookup table), floats as 0-1."""
    a = np.asarray(x)
    if a.dtype == np.uint8:
        return _LUT[a]
    return _decode(a.astype(np.float64))


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    """Linear light (0-1) to encoded sRGB (0-1)."""
    a = np.asarray(x, dtype=np.float64)
    return np.where(a <= 0.0031308, 12.92 * a, 1.055 * np.power(np.clip(a, 0, None), 1 / 2.4) - 0.055)
