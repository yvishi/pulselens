"""Fetch the browser face model and MediaPipe wasm into web/public/models/ (gitignored). Stdlib only.

Downloads face_landmarker.task if missing and copies web/node_modules/@mediapipe/tasks-vision/wasm/* into
web/public/models/wasm/. Run after `python scripts/dev.py setup`.
"""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "models"
WASM_SRC = ROOT / "web" / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


def fetch_model() -> None:
    target = OUT / "face_landmarker.task"
    if target.exists() and target.stat().st_size > 0:
        print(f"ok      {target.relative_to(ROOT)}")
        return
    tmp = target.with_suffix(".part")
    print(f"fetch   {MODEL_URL}")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(target)
    print(f"wrote   {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")


def copy_wasm() -> None:
    if not WASM_SRC.is_dir():
        sys.exit(f"missing {WASM_SRC}; run `python scripts/dev.py setup` first")
    dest = OUT / "wasm"
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(WASM_SRC.iterdir()):
        if f.is_file():
            shutil.copy2(f, dest / f.name)
            print(f"copied  {(dest / f.name).relative_to(ROOT)}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fetch_model()
    copy_wasm()


if __name__ == "__main__":
    main()
