"""Face regions per frame, and the MediaPipe landmarker that finds them.

`regions_from_landmarks` is pure geometry on landmark positions in pixels (ported unchanged from the old repo):
- skin: forehead + left and right cheek, boxes placed between the landmarks so eyes, brows and lips stay out
- left/right cheek: by image side (image left = the person's right in an unmirrored camera frame)
- neck: a box below the chin, 0.6 face widths wide, 0.05 to 0.45 face heights below the chin, clipped to the frame
- background: the frame minus the face box dilated 1.6x and minus a bottom-centre body block

`Landmarker` wraps MediaPipe FaceLandmarker in VIDEO mode and returns all 478 normalised landmarks plus the head pose,
in the shape of one landmarks.jsonl line (CONTRACT section 5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pulselens.analysis.vision.pose import yaw_pitch

# MediaPipe face-mesh indices
FOREHEAD_TOP, CHIN, SIDE_A, SIDE_B = 10, 152, 234, 454
BROWS = (70, 63, 105, 66, 107, 336, 296, 334, 293, 300)
BROW_INNER_A, BROW_INNER_B = 105, 334
LOWER_LIDS = (145, 374)
CHEEKS = (50, 280)
LIPS = (13, 14)
LANDMARKS_USED: tuple[int, ...] = tuple(
    sorted({FOREHEAD_TOP, CHIN, SIDE_A, SIDE_B, *BROWS, *LOWER_LIDS, *CHEEKS, *LIPS})
)
N_LANDMARKS = 478
# Face proportions for turn.identity: 10 distances between fixed points, in units of the outer eye-corner distance
# (so they do not change with scale, position or roll). Lip opening is left out: it changes with speech.
EYE_OUTER_A, EYE_OUTER_B = 33, 263
GEOMETRY_PAIRS: tuple[tuple[int, int], ...] = (
    (133, 362),  # inner eye corners
    (33, 133),  # one eye's width
    (263, 362),  # the other eye's width
    (168, 1),  # nose bridge to nose tip
    (98, 327),  # nose width
    (61, 291),  # mouth corners
    (1, 152),  # nose tip to chin
    (FOREHEAD_TOP, 1),  # forehead to nose tip
    (SIDE_A, SIDE_B),  # face width
    (172, 397),  # jaw width
)

NECK_WIDTH = 0.6  # face widths
NECK_TOP, NECK_BOTTOM = 0.05, 0.45  # face heights below the chin
BACKGROUND_DILATE = 1.6
BODY_HALF_WIDTH = 1.25  # face widths either side of the face centre, from the chin down
CHEEK_SIZE = 0.18  # face widths


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)

    def clip(self, w: int, h: int) -> Box:
        return Box(min(max(self.x0, 0), w), min(max(self.y0, 0), h), min(max(self.x1, 0), w), min(max(self.y1, 0), h))

    def scaled(self, f: float) -> Box:
        cx, cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        hw, hh = (self.x1 - self.x0) * f / 2, (self.y1 - self.y0) * f / 2
        return Box(cx - hw, cy - hh, cx + hw, cy + hh)

    def slices(self) -> tuple[slice, slice]:
        """Integer pixel slices (rows, cols) of this box."""
        return slice(round(self.y0), round(self.y1)), slice(round(self.x0), round(self.x1))

    def xywh(self) -> tuple[float, float, float, float]:
        return self.x0, self.y0, self.x1 - self.x0, self.y1 - self.y0


@dataclass(frozen=True)
class FaceRegions:
    face_box: Box
    forehead: Box
    left_cheek: Box
    right_cheek: Box
    neck: Box
    neck_coverage: float
    background_exclude: tuple[Box, ...]

    @property
    def skin(self) -> tuple[Box, ...]:
        return (self.forehead, self.left_cheek, self.right_cheek)


def regions_from_landmarks(lm: Mapping[int, tuple[float, float]], w: int, h: int) -> FaceRegions:
    """Regions from pixel landmark positions (at least LANDMARKS_USED)."""
    xs = [p[0] for p in lm.values()]
    ys = [p[1] for p in lm.values()]
    face = Box(min(xs), min(ys), max(xs), max(ys))
    fw = abs(lm[SIDE_B][0] - lm[SIDE_A][0]) or (face.x1 - face.x0)
    fh = abs(lm[CHIN][1] - lm[FOREHEAD_TOP][1]) or (face.y1 - face.y0)
    chin_x, chin_y = lm[CHIN]

    brow_top = min(lm[i][1] for i in BROWS)
    top = lm[FOREHEAD_TOP][1]
    band = max(brow_top - top, 1.0)
    fx = sorted((lm[BROW_INNER_A][0], lm[BROW_INNER_B][0]))
    forehead = Box(fx[0], top + 0.2 * band, fx[1], brow_top - 0.2 * band)

    lid_y = max(lm[i][1] for i in LOWER_LIDS)
    lip_y = min(lm[i][1] for i in LIPS)
    half = CHEEK_SIZE * fw / 2
    cheeks = []
    for i in CHEEKS:
        cx, cy = lm[i]
        y0 = max(cy - half, lid_y + 0.1 * (lip_y - lid_y))
        y1 = min(cy + half, lip_y - 0.1 * (lip_y - lid_y))
        cheeks.append(Box(cx - half, y0, cx + half, y1))
    left_cheek, right_cheek = sorted(cheeks, key=lambda b: b.x0)

    nominal_neck = Box(
        chin_x - NECK_WIDTH * fw / 2, chin_y + NECK_TOP * fh, chin_x + NECK_WIDTH * fw / 2, chin_y + NECK_BOTTOM * fh
    )
    neck = nominal_neck.clip(w, h)
    coverage = neck.area / nominal_neck.area if nominal_neck.area else 0.0

    centre_x = (face.x0 + face.x1) / 2
    body = Box(centre_x - BODY_HALF_WIDTH * fw, chin_y, centre_x + BODY_HALF_WIDTH * fw, h)
    return FaceRegions(
        face_box=face,
        forehead=forehead.clip(w, h),
        left_cheek=left_cheek.clip(w, h),
        right_cheek=right_cheek.clip(w, h),
        neck=neck,
        neck_coverage=coverage,
        background_exclude=(face.scaled(BACKGROUND_DILATE), body),
    )


def face_geometry(lm: Mapping[int, tuple[float, float]]) -> np.ndarray:
    """GEOMETRY_PAIRS distances over the outer eye-corner distance; NaN when a point is missing or the eyes coincide."""
    def dist(a: int, b: int) -> float:
        if a not in lm or b not in lm:
            return np.nan
        return float(np.hypot(lm[a][0] - lm[b][0], lm[a][1] - lm[b][1]))

    unit = dist(EYE_OUTER_A, EYE_OUTER_B)
    if not unit > 0:
        return np.full(len(GEOMETRY_PAIRS), np.nan)
    return np.array([dist(a, b) / unit for a, b in GEOMETRY_PAIRS])


def to_pixels(landmarks: Sequence[Sequence[float]], w: int, h: int) -> dict[int, tuple[float, float]]:
    """landmarks.jsonl `landmarks` ([[x, y, z] x 478], normalised) to pixel positions by landmark index."""
    return {i: (float(p[0]) * w, float(p[1]) * h) for i, p in enumerate(landmarks)}


class Landmarker:
    """MediaPipe FaceLandmarker in VIDEO mode, one face, with the facial transformation matrix."""

    def __init__(self, model_path: Path) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        self._last_ts = -1

    def detect(self, rgb: np.ndarray, t_ms: float) -> dict | None:
        """{landmarks: [[x, y, z] x 478], yaw, pitch} for one RGB uint8 frame, or None without a face."""
        ts = max(int(round(t_ms)), self._last_ts + 1)  # MediaPipe needs strictly increasing timestamps
        self._last_ts = ts
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._landmarker.detect_for_video(image, ts)
        if not result.face_landmarks:
            return None
        pts = result.face_landmarks[0]
        yaw = pitch = None
        if result.facial_transformation_matrixes:
            yaw, pitch = yaw_pitch(np.asarray(result.facial_transformation_matrixes[0]))
        return {"landmarks": [[p.x, p.y, p.z] for p in pts], "yaw": yaw, "pitch": pitch}

    def close(self) -> None:
        self._landmarker.close()
