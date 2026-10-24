"""The Self-Blended Images detector (Shiohara & Yamasaki, CVPR 2022), for visual.sbi. EfficientNet-B4 trained on
FF++ c23; the weights are research-only (disclosed in the deck) and never committed: `models/sbi/FFc23.tar`.

Preprocessing matches the SBI repo's inference code (github.com/mapooon/SelfBlendedImages, src/inference):
- crop: the face box grown by 1/8 of its width on the left and right and 1/8 of its height above and below
  (`crop_face(..., crop_by_bbox=True, phase="test")`), clipped to the frame, **not** made square;
- `cv2.resize` to 380x380 (bilinear), RGB, CHW, float 0..1 (no mean/std normalisation);
- P(fake) = softmax(logits)[:, 1]. SBI's own video score is the mean over frames.
The network is built with `EfficientNet.from_name` (same architecture as SBI's `from_pretrained(..., advprop=True)`)
so nothing is downloaded: every weight comes from the checkpoint. The checkpoint is read with
`torch.load(weights_only=True)`: no pickled code from a downloaded file ever runs.

torch and efficientnet_pytorch are imported only when the weights exist, so the analysis runs without them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from pulselens.config import ROOT

WEIGHTS = ROOT / "models" / "sbi" / "FFc23.tar"
SIZE = 380
MARGIN = 1 / 8  # of the box's width (left, right) and height (top, bottom), SBI's test-phase crop

log = logging.getLogger("pulselens.analysis")

Predict = Callable[[np.ndarray], np.ndarray]  # (n, 3, 380, 380) float32 0..1 -> (n,) P(fake)


def crop(rgb: np.ndarray, box_xywh: tuple[float, float, float, float]) -> np.ndarray:
    """SBI's test-phase face crop of an RGB uint8 frame, resized to SIZE x SIZE (HWC uint8)."""
    x, y, w, h = box_xywh
    x0, y0, x1, y1 = x, y, x + w, y + h
    hh, ww = rgb.shape[:2]
    y0n, y1n = max(0, int(y0 - h * MARGIN)), min(hh, int(y1 + h * MARGIN) + 1)
    x0n, x1n = max(0, int(x0 - w * MARGIN)), min(ww, int(x1 + w * MARGIN) + 1)
    return cv2.resize(rgb[y0n:y1n, x0n:x1n], dsize=(SIZE, SIZE))


def to_input(crops: list[np.ndarray]) -> np.ndarray:
    """HWC uint8 crops -> the network input, (n, 3, SIZE, SIZE) float32 0..1."""
    return np.stack([c.transpose(2, 0, 1) for c in crops]).astype(np.float32) / 255.0


class SbiModel:
    def __init__(self, predict: Predict) -> None:
        self._predict = predict

    @classmethod
    def load(cls, path: Path = WEIGHTS) -> SbiModel | None:
        """None if the file is missing, torch or efficientnet_pytorch is not installed, or the checkpoint does not
        load (the reason goes to the log)."""
        if not Path(path).exists():
            return None
        try:
            import torch
            from efficientnet_pytorch import EfficientNet
        except ImportError:
            log.warning("SBI weights found but torch / efficientnet_pytorch are not installed")
            return None
        try:
            net = EfficientNet.from_name("efficientnet-b4", num_classes=2)
            state = torch.load(path, map_location="cpu", weights_only=True)
            state = state.get("model", state)
            net.load_state_dict({k.removeprefix("net."): v for k, v in state.items()})
            net.eval()
        except Exception:  # noqa: BLE001 -- a bad checkpoint means no model, never a crash
            log.exception("could not load the SBI weights from %s", path)
            return None

        def predict(x: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                return net(torch.from_numpy(x)).softmax(1)[:, 1].numpy().astype(np.float64)

        return cls(predict)

    def score(self, crops: list[np.ndarray]) -> np.ndarray:
        """RGB uint8 SIZE x SIZE crops -> P(fake) per crop."""
        if not crops:
            return np.zeros(0)
        return np.asarray(self._predict(to_input(crops)), dtype=np.float64).reshape(-1)


_cache: dict[tuple[Path, float | None], SbiModel | None] = {}


def get_model(path: Path = WEIGHTS) -> SbiModel | None:
    """Loaded once per process and file version (the network takes seconds to build): weights installed or
    replaced while the server runs are picked up, and a checkpoint that fails to load is not retried."""
    path = Path(path)
    key = (path, path.stat().st_mtime if path.exists() else None)
    if key not in _cache:
        _cache[key] = SbiModel.load(path)
    return _cache[key]
