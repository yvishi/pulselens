"""web/src/console/reasonText.ts mirrors the mode.* sentences of engine/reason_text.py word for word."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pulselens.engine.reason_text import REASON_TEXT

TS = Path(__file__).resolve().parents[3] / "web" / "src" / "console" / "reasonText.ts"


def test_console_mode_reasons_match_the_server() -> None:
    pairs = re.findall(r'^\s*("mode\.[^"]+"):\s*(".*?"),\s*$', TS.read_text(encoding="utf-8"), re.M)
    ts = {json.loads(k): json.loads(v) for k, v in pairs}
    assert ts == {k: v for k, v in REASON_TEXT.items() if k.startswith("mode.")}
