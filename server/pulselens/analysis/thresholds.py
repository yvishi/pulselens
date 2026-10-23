"""Thresholds per check: calibrated values (G9, thresholds.calibrated.yaml) win over the provisional ones."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pulselens.contracts import ThresholdSource

HERE = Path(__file__).parent
PROVISIONAL = HERE / "thresholds.yaml"
CALIBRATED = HERE / "thresholds.calibrated.yaml"


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class Thresholds:
    def __init__(self, provisional: dict[str, Any], calibrated: dict[str, Any] | None = None) -> None:
        self._provisional = provisional
        self._calibrated = calibrated or {}

    @classmethod
    def load(cls, provisional: Path = PROVISIONAL, calibrated: Path = CALIBRATED) -> Thresholds:
        return cls(_read(provisional), _read(calibrated))

    def params(self, key: str) -> dict[str, Any]:
        """Every parameter of a check or section (e.g. "quality", "light.response"), calibrated values on top."""
        return {**(self._provisional.get(key) or {}), **(self._calibrated.get(key) or {})}

    def source(self, check_id: str) -> ThresholdSource:
        return "calibrated" if "flag_at" in (self._calibrated.get(check_id) or {}) else "provisional"

    def flag_at(self, check_id: str, default: float = 0.5) -> float:
        return float(self.params(check_id).get("flag_at", default))

    def voting(self, check_id: str) -> bool:
        return bool(self.params(check_id).get("voting", True))
