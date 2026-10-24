"""Freeze (K10b): hashes of config and thresholds plus the voting-off list; set B runs only against it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FROZEN_INPUTS = [
    "config.yaml",
    "server/pulselens/analysis/thresholds.yaml",
    "server/pulselens/analysis/thresholds.calibrated.yaml",
]


def check_ids(arg: str) -> set[str]:
    """--voting-off "a, b" → {"a", "b"}."""
    return {part.strip() for part in arg.split(",") if part.strip()}


def _hashes(root: Path) -> dict[str, str]:
    """sha256 hex of each frozen input under root, or "missing" when the file is absent."""
    out: dict[str, str] = {}
    for rel in FROZEN_INPUTS:
        path = root / rel
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
    return out


def write_frozen(voting_off: list[str], root: Path = Path(".")) -> Path:
    """Write root/eval/FROZEN with the input hashes and the sorted voting-off list; return its path."""
    path = root / "eval" / "FROZEN"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"files": _hashes(root), "voting_off": sorted(voting_off)}, indent=2))
    return path


def frozen_ok(root: Path = Path(".")) -> bool:
    """True only when root/eval/FROZEN is valid JSON and its recorded hashes match the inputs now."""
    try:
        data = json.loads((root / "eval" / "FROZEN").read_text())
        return isinstance(data, dict) and data.get("files") == _hashes(root)
    except (OSError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    """Write eval/FROZEN in the current directory and print the short hashes."""
    parser = argparse.ArgumentParser(prog="python -m eval.freeze", description=__doc__)
    parser.add_argument("--voting-off", default="", help="comma-separated check ids excluded from voting")
    args = parser.parse_args(argv)
    path = write_frozen(sorted(check_ids(args.voting_off)), root=Path("."))
    files = json.loads(path.read_text())["files"]
    print(f"wrote {path}: " + ", ".join(f"{k} {v[:12]}" for k, v in files.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
