"""config.yaml and the .env settings, read once."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"
PLACEHOLDER = "change-me"

log = logging.getLogger("pulselens")


@lru_cache
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_env_file(path: Path) -> dict[str, str]:
    """KEY=value lines of .env; the process environment wins over the file."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            out[key.strip()] = value.strip()
    return out


@dataclass(frozen=True)
class Settings:
    agent_passcode: str
    data_dir: Path
    fake_analysis: bool
    delete_frames_on_decision: bool = True

    @property
    def uses_placeholder(self) -> bool:
        return self.agent_passcode == PLACEHOLDER


def get_settings(env_file: Path = ROOT / ".env") -> Settings:
    env = {**_read_env_file(env_file), **os.environ}
    data_dir = Path(env.get("PULSE_DATA_DIR", "data/sessions"))
    cfg = load_config() if CONFIG_PATH.exists() else {}
    default_del = cfg.get("session", {}).get("delete_frames_on_decision", True)
    del_frames = env.get("PULSE_DELETE_FRAMES_ON_DECISION")
    delete_frames = del_frames == "1" if del_frames is not None else default_del
    settings = Settings(
        agent_passcode=env.get("AGENT_PASSCODE", PLACEHOLDER),
        data_dir=data_dir if data_dir.is_absolute() else ROOT / data_dir,
        fake_analysis=env.get("PULSE_FAKE_ANALYSIS", "0") == "1",
        delete_frames_on_decision=bool(delete_frames),
    )
    if settings.uses_placeholder:
        log.warning("AGENT_PASSCODE is still %r; set a real value in .env", PLACEHOLDER)
    return settings
