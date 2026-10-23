"""Markdown evaluation report (K10b): frozen set B headline, set A tuning block, small-sample disclaimer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval.freeze import check_ids, frozen_ok
from eval.load import load_sessions
from eval.run import Metrics, _lines, metrics
from pulselens.config import get_settings

DISCLAIMER = "Small samples: feasibility evidence, not production accuracy."


def _block(m: Metrics, title: str) -> list[str]:
    head, *rest = _lines(title, m)
    return [f"### {head}", *(f"- {line.strip()}" for line in rest)]


def render(headline: Metrics | None, tuning: Metrics | None) -> str:
    """Markdown report: title, disclaimer, set B headline block (or not-run line), set A tuning block (or none)."""
    out = ["# PulseLens evaluation", "", DISCLAIMER, "", "## Headline (set B, frozen)", ""]
    out += _block(headline, "Set B") if headline is not None else ["Set B not run: eval/FROZEN missing or stale."]
    out += ["", "## Tuning set (A)", ""]
    out += _block(tuning, "Set A") if tuning is not None else ["No set A sessions."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write report.md to --out and print its path."""
    ap = argparse.ArgumentParser(prog="python -m eval.report", description=__doc__)
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--voting-off", default="", help="comma-separated check ids measured but not voting")
    ap.add_argument("--out", type=Path, default=Path("eval/out"))
    args = ap.parse_args(argv)
    data = args.data if args.data is not None else get_settings().data_dir
    voting_off = check_ids(args.voting_off)
    a = load_sessions(data, "A")
    b = load_sessions(data, "B") if frozen_ok() else []
    text = render(metrics(b, voting_off) if b else None, metrics(a, voting_off) if a else None)
    path = args.out / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
