"""Purge CLI. Demo sessions: `python scripts/purge.py [--data PATH]`.
After the event: `python scripts/purge.py --all-volunteers [--data PATH]` (asks you to type DELETE)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from pulselens.config import get_settings  # noqa: E402
from pulselens.engine.purge import purge  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete PulseLens sessions.")
    parser.add_argument("--data", type=Path, default=None, help="sessions folder (default: configured data_dir)")
    parser.add_argument("--all-volunteers", action="store_true", help="delete every labelled session")
    args = parser.parse_args(argv)
    data = args.data if args.data is not None else get_settings().data_dir
    if not args.all_volunteers:
        deleted = purge(data, now_ms=time.time() * 1000)
        print(f"deleted {len(deleted)} demo sessions")
        return 0
    if input("Type DELETE to delete every labelled session: ").strip() != "DELETE":
        print("cancelled")
        return 1
    deleted = purge(data, now_ms=time.time() * 1000, labelled=True)
    print(f"deleted {len(deleted)} labelled sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
