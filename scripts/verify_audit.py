"""Verify a session's audit chain: python scripts/verify_audit.py data/sessions/<id>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from pulselens.engine.audit import verify  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a session's hash-chained audit.jsonl.")
    parser.add_argument("session_dir", type=Path)
    args = parser.parse_args(argv)
    session_dir: Path = args.session_dir
    ok, bad = verify(session_dir)
    if ok:
        print(f"ok: {session_dir}")
        return 0
    print(f"tampered: {session_dir}: first bad line {bad}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
