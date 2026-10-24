"""ArcFace face embeddings, for turn.identity (G10c): InsightFace's `buffalo_l` recognition model `w600k_r50.onnx`
(ResNet-50 trained on WebFace600K, 112x112 input, 512-d output). The model is for non-commercial research only and
is never committed: `models/arcface/w600k_r50.onnx`, extracted from
github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip.

Alignment and preprocessing match InsightFace (python-package/insightface/utils/face_align.py and
model_zoo/arcface_onnx.py):
- 5 points (left eye, right eye, nose tip, left and right mouth corner, by image side) mapped onto the standard
  ArcFace 112x112 template by a similarity transform (rotation, uniform scale, shift) fitted by least squares;
  InsightFace takes the points from its detector, here they come from the MediaPipe landmarks: eye centres = the
  midpoint of the eye corners 33/133 and 263/362, nose tip 1, mouth corners 61/291;
- RGB, (pixel - 127.5) / 127.5, NCHW float32; the embedding is L2-normalised, so cosine similarity = dot product.

onnxruntime is imported only when the model file exists, so the analysis runs without it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import cv2
import numpy as np

from pulselens.config import ROOT

WEIGHTS = ROOT / "models" / "arcface" / "w600k_r50.onnx"
SIZE = 112
# InsightFace's arcface_dst: where the 5 points land in the 112x112 crop (image left eye first)
TEMPLATE = np.array(
    [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]],
    dtype=np.float32,
)
# MediaPipe face-mesh indices. Side A (33, 133, 61) is the person's right, side B (263, 362, 291) the left.
EYE_A, EYE_B = (33, 133), (263, 362)
NOSE_TIP = 1
MOUTH_A, MOUTH_B = 61, 291

log = logging.getLogger("pulselens.analysis")

Predict = Callable[[np.ndarray], np.ndarray]  # (n, 3, 112, 112) float32 -> (n, 512) raw embeddings


def five_points(pixels: Mapping[int, Sequence[float]]) -> np.ndarray | None:
    """The 5 alignment points in pixels, (5, 2) float32 in template order (by image side, so a mirrored frame
    works too), or None when a landmark is missing."""
    needed = (*EYE_A, *EYE_B, NOSE_TIP, MOUTH_A, MOUTH_B)
    if any(i not in pixels for i in needed):
        return None
    p = {i: np.asarray(pixels[i][:2], dtype=np.float64) for i in needed}
    eye_a, eye_b = (p[EYE_A[0]] + p[EYE_A[1]]) / 2, (p[EYE_B[0]] + p[EYE_B[1]]) / 2
    pts = [eye_a, eye_b, p[NOSE_TIP], p[MOUTH_A], p[MOUTH_B]]
    if eye_a[0] > eye_b[0]:  # side A on the image right: swap to keep image-left first
        pts = [eye_b, eye_a, p[NOSE_TIP], p[MOUTH_B], p[MOUTH_A]]
    out = np.array(pts, dtype=np.float32)
    return out if np.isfinite(out).all() else None


def align(rgb: np.ndarray, points: np.ndarray) -> np.ndarray | None:
    """The 112x112 ArcFace crop (HWC uint8) of an RGB frame, or None when no transform fits. The very large
    reprojection threshold keeps all 5 points as inliers, so the result is the least-squares similarity transform
    (InsightFace's estimate_norm), refined by Levenberg-Marquardt."""
    m, _ = cv2.estimateAffinePartial2D(points, TEMPLATE, method=cv2.RANSAC, ransacReprojThreshold=1e6)
    if m is None or not np.isfinite(m).all():
        return None
    return cv2.warpAffine(rgb, m, (SIZE, SIZE), borderValue=0.0)


def to_input(crops: list[np.ndarray]) -> np.ndarray:
    """HWC uint8 RGB crops -> the network input, (n, 3, 112, 112) float32 in -1..1."""
    return (np.stack([c.transpose(2, 0, 1) for c in crops]).astype(np.float32) - 127.5) / 127.5


class ArcFaceModel:
    def __init__(self, predict: Predict) -> None:
        self._predict = predict

    @classmethod
    def load(cls, path: Path = WEIGHTS) -> ArcFaceModel | None:
        """None if the file is missing, onnxruntime is not installed, or the model does not load (logged)."""
        if not Path(path).exists():
            return None
        try:
            import onnxruntime as ort
        except ImportError:
            log.warning("ArcFace model found but onnxruntime is not installed")
            return None
        try:
            opts = ort.SessionOptions()
            opts.log_severity_level = 3  # the graph declares a batch of 1; larger batches run but log a warning
            session = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
            name = session.get_inputs()[0].name
        except Exception:  # noqa: BLE001 -- a bad model file means no model, never a crash
            log.exception("could not load the ArcFace model from %s", path)
            return None

        def predict(x: np.ndarray) -> np.ndarray:
            return session.run(None, {name: x})[0]

        return cls(predict)

    def embed(self, crops: list[np.ndarray]) -> np.ndarray:
        """Aligned RGB uint8 112x112 crops -> L2-normalised embeddings, (n, d) float64."""
        if not crops:
            return np.zeros((0, 512))
        e = np.asarray(self._predict(to_input(crops)), dtype=np.float64).reshape(len(crops), -1)
        return e / np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-12)


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of the mean embeddings of two sets of L2-normalised embeddings, -1..1."""
    ma, mb = np.mean(a, axis=0), np.mean(b, axis=0)
    return float(ma @ mb / max(float(np.linalg.norm(ma) * np.linalg.norm(mb)), 1e-12))


_cache: dict[tuple[Path, float | None], ArcFaceModel | None] = {}


def get_model(path: Path | None = None) -> ArcFaceModel | None:
    """Loaded once per process and file version: a model installed or replaced while the server runs is picked up,
    and one that fails to load is not retried. `path` defaults to WEIGHTS read at call time (tests and measuring
    scripts may point it elsewhere)."""
    path = Path(WEIGHTS if path is None else path)
    key = (path, path.stat().st_mtime if path.exists() else None)
    if key not in _cache:
        _cache[key] = ArcFaceModel.load(path)
    return _cache[key]
