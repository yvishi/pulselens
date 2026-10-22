"""Head pose from MediaPipe's facial transformation matrix.

The browser gets the matrix as a column-major array `m` and computes `yaw = atan2(m[8], m[10])` (docs/tasks/yash.md
Y2). The Python API returns the same matrix as a row-major 4x4 array `M`, where m[8] = M[0, 2] and m[10] = M[2, 2],
so both sides compute the same angle. Sign per CONTRACT section 1: positive = the person turns to their own left.
"""

from __future__ import annotations

import math

import numpy as np


def yaw_pitch(matrix: np.ndarray) -> tuple[float | None, float | None]:
    """(yaw, pitch) in degrees from a row-major 4x4 transformation matrix; (None, None) if it is not one."""
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape != (4, 4) or not np.all(np.isfinite(m[:3, :3])):
        return None, None
    yaw = math.degrees(math.atan2(m[0, 2], m[2, 2]))
    pitch = math.degrees(math.atan2(-m[1, 2], math.hypot(m[0, 2], m[2, 2])))
    return yaw, pitch


def rotation_y(yaw_deg: float) -> np.ndarray:
    """A row-major 4x4 matrix whose yaw is `yaw_deg` (for tests and synthetic sessions)."""
    a = math.radians(yaw_deg)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return m
