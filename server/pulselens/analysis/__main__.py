"""`python -m pulselens.analysis <session_dir> [--plots]`: run the analysis on one bundle and print the results.

--plots writes a PNG of every result's plot to <session_dir>/analysis/.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pulselens.analysis import analyze
from pulselens.contracts import CheckResult


def table(results: list[CheckResult]) -> str:
    rows = [("check_id", "family", "status", "risk", "flag", "explanation")]
    for r in results:
        risk = f"{r.risk:.2f}" if r.risk is not None else "-"
        rows.append((r.check_id, r.family, r.status, risk, "FLAG" if r.flag else "", r.explanation))
    widths = [max(len(row[k]) for row in rows) for k in range(5)]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(row[:5], widths, strict=True)) + "  " + row[5]
                     for row in rows)


def write_plots(results: list[CheckResult], out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    written = []
    for r in results:
        if r.plot is None:
            continue
        fig, ax = plt.subplots(figsize=(8, 3))
        for name, points in r.plot.series.items():
            if points:
                xs, ys = zip(*points, strict=True)
                ax.plot(xs, ys, label=name)
        for t_ms, label in r.plot.markers:
            ax.axvline(t_ms, color="grey", linewidth=0.8)
            ax.annotate(label, (t_ms, 1), xycoords=("data", "axes fraction"), fontsize=7)
        ax.set_title(f"{r.check_id} ({r.plot.kind})")
        ax.set_xlabel("t (ms)")
        ax.legend(loc="upper right", fontsize=7)
        path = out / f"{r.check_id}{'-' + r.window_id if r.window_id else ''}.png"
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pulselens.analysis", description=__doc__)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--plots", action="store_true", help="write PNGs of every plot to <session_dir>/analysis/")
    args = ap.parse_args(argv)
    if not args.session_dir.is_dir():
        print(f"{args.session_dir} is not a directory", file=sys.stderr)
        return 2
    results = analyze(args.session_dir)
    print(table(results) if results else "No checks ran.")
    if args.plots:
        for path in write_plots(results, args.session_dir / "analysis"):
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
