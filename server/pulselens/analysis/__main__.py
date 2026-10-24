"""`python -m pulselens.analysis <session_dir> [--plots]`: run the analysis on one bundle and print the results.

--plots writes a PNG of every result's plot to <session_dir>/analysis/.
--all treats the folder as a data folder (data/sessions) and runs every session in it (G11), then reports what to
fix before trusting the checks on real sessions: checks that crashed (`quality.check_error`), checks that abstain on
more than half of the genuine sessions, flags on genuine sessions, and the time per session.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pulselens.analysis import analyze
from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult

MAX_GENUINE_ABSTAIN = 0.5


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


def batch(data_dir: Path) -> str:
    """Every session folder under `data_dir`: analysed, timed, and summarised per check."""
    lines, seconds = [], []
    crashed: dict[str, list[str]] = defaultdict(list)
    genuine: dict[str, list[CheckResult]] = defaultdict(list)
    n_genuine = 0
    for path in sorted(p for p in data_dir.iterdir() if (p / "session.json").exists()):
        label = load_bundle(path).label
        kind = label.kind if label is not None else "unlabelled"
        start = time.perf_counter()
        results = analyze(path)
        seconds.append(time.perf_counter() - start)
        n_genuine += kind == "genuine"
        flags = [r.check_id for r in results if r.flag]
        abstains = [r.check_id for r in results if r.status == "abstain"]
        for r in results:
            if "quality.check_error" in r.reason_codes:
                crashed[r.check_id].append(path.name)
            if kind == "genuine":
                genuine[r.check_id].append(r)
        lines.append(f"{path.name}  {kind}  {seconds[-1]:.1f} s  flags: {', '.join(flags) or '-'}  "
                     f"abstains: {', '.join(abstains) or '-'}")
    if not seconds:
        return f"No sessions (folders with session.json) in {data_dir}."
    lines.append(f"\n{len(seconds)} sessions ({n_genuine} genuine); time per session: median "
                 f"{sorted(seconds)[len(seconds) // 2]:.1f} s, max {max(seconds):.1f} s")
    for check_id, ids in sorted(crashed.items()):
        lines.append(f"CRASHED  {check_id} in {len(ids)} sessions: {', '.join(ids)}")
    for check_id, rs in sorted(genuine.items()):
        abstained = sum(r.status == "abstain" for r in rs) / len(rs)
        flagged = sum(r.flag for r in rs)
        if abstained > MAX_GENUINE_ABSTAIN:
            lines.append(f"ABSTAINS {check_id} on {abstained:.0%} of genuine sessions")
        if flagged:
            lines.append(f"FLAGS    {check_id} on {flagged} of {len(rs)} genuine sessions")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pulselens.analysis", description=__doc__)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--plots", action="store_true", help="write PNGs of every plot to <session_dir>/analysis/")
    ap.add_argument("--all", action="store_true", help="run every session under the folder (e.g. data/sessions)")
    args = ap.parse_args(argv)
    if not args.session_dir.is_dir():
        print(f"{args.session_dir} is not a directory", file=sys.stderr)
        return 2
    if args.all:
        print(batch(args.session_dir))
        return 0
    results = analyze(args.session_dir)
    print(table(results) if results else "No checks ran.")
    if args.plots:
        for path in write_plots(results, args.session_dir / "analysis"):
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
