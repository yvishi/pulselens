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

    def param(self, section: str, key: str) -> Any:
        """One value, calibrated over provisional. There are no code defaults: a key missing from thresholds.yaml is a
        KeyError, which a check's `guarded` turns into an abstain with `quality.check_error`."""
        values = self.params(section)
        if key not in values:
            raise KeyError(f"{section}.{key} is not in thresholds.yaml")
        return values[key]

    def source(self, check_id: str) -> ThresholdSource:
        return "calibrated" if "flag_at" in (self._calibrated.get(check_id) or {}) else "provisional"

    def flag_at(self, check_id: str) -> float:
        return float(self.param(check_id, "flag_at"))

    def voting(self, check_id: str) -> bool:
        """An optional switch, not a value: absent means the check votes (`voting: false` is set at S3)."""
        return bool(self.params(check_id).get("voting", True))
