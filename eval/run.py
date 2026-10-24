"""APCER/BPCER, retry and abstain rates, latency (K10b); set B headline only after eval/FROZEN."""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from eval.freeze import check_ids, frozen_ok
from eval.load import EvalSession, load_sessions
from pulselens.config import get_settings
from pulselens.contracts import Decision
from pulselens.engine.fusion import fuse


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (default 95%) for x successes of n, clamped to [0, 1]; (0.0, 1.0) when n == 0."""
    if n == 0:
        return 0.0, 1.0
    p = x / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def refuse(s: EvalSession, voting_off: set[str]) -> Decision:
    """Re-run fusion on a session's stored results with the "measured, not voting" checks dropped first."""
    decided_at_ms = s.decision.decided_at_ms if s.decision else 0
    return fuse([r for r in s.results if r.check_id not in voting_off], s.plan, s.attempt,
                decided_at_ms=decided_at_ms)


@dataclass(frozen=True)
class Metrics:
    apcer: dict[str, tuple[int, int]]  # per attack kind: (sessions with outcome PASS, sessions of that kind)
    bpcer: tuple[int, int]  # (genuine with outcome HUMAN_REVIEW, genuine)
    retry: tuple[int, int]  # (genuine with outcome RETRY_STEP_UP, genuine)
    abstain: dict[str, tuple[int, int]]  # per family "A".."D": (sessions whose family state is abstained, sessions)
    latency_ms: tuple[float, float] | None  # (median, p95) of decision.decided_at_ms - completed_at_ms


def metrics(sessions: list[EvalSession], voting_off: set[str]) -> Metrics:
    """APCER per attack kind, BPCER and retry rate on genuine sessions, abstain rate per family, stored latency."""
    decisions = [(s, refuse(s, voting_off)) for s in sessions]
    genuine = [d for s, d in decisions if s.label.kind == "genuine"]
    kinds = sorted({s.label.kind for s in sessions} - {"genuine"})
    apcer = {}
    for kind in kinds:
        attacks = [d for s, d in decisions if s.label.kind == kind]
        apcer[kind] = (sum(d.outcome == "PASS" for d in attacks), len(attacks))
    abstain = {}
    for fam in ("A", "B", "C", "D"):
        n = sum(f.state == "abstained" for _, d in decisions for f in d.families if f.family == fam)
        abstain[fam] = (n, len(decisions))
    waits = sorted(s.decision.decided_at_ms - s.completed_at_ms for s in sessions
                   if s.decision is not None and s.completed_at_ms is not None)
    latency = (float(statistics.median(waits)), float(waits[math.ceil(0.95 * len(waits)) - 1])) if waits else None
    return Metrics(
        apcer=apcer,
        bpcer=(sum(d.outcome == "HUMAN_REVIEW" for d in genuine), len(genuine)),
        retry=(sum(d.outcome == "RETRY_STEP_UP" for d in genuine), len(genuine)),
        abstain=abstain,
        latency_ms=latency,
    )


def _rate(x: int, n: int) -> str:
    lo, hi = wilson(x, n)
    return f"{x} of {n} [{lo:.2f}-{hi:.2f}]"


def _lines(title: str, m: Metrics) -> list[str]:
    """One printable block: title, APCER per attack kind, BPCER, retry, abstain per family, latency."""
    out = [title]
    out += [f"  APCER {kind}: {_rate(x, n)}" for kind, (x, n) in m.apcer.items()]
    out.append(f"  BPCER: {_rate(*m.bpcer)}")
    out.append(f"  retry: {_rate(*m.retry)}")
    out += [f"  abstain {fam}: {_rate(x, n)}" for fam, (x, n) in m.abstain.items()]
    if m.latency_ms is None:
        out.append("  latency n/a")
    else:
        out.append(f"  latency median {m.latency_ms[0]:.0f} ms, p95 {m.latency_ms[1]:.0f} ms")
    return out


def main(argv: list[str] | None = None) -> int:
    """Print APCER/BPCER/retry/abstain/latency with Wilson intervals, overall and per device, light and mode."""
    ap = argparse.ArgumentParser(prog="python -m eval.run", description=__doc__)
    ap.add_argument("--set", dest="set_", choices=["A", "B"], required=True)
    ap.add_argument("--voting-off", default="", help="comma-separated check ids measured but not voting")
    ap.add_argument("--data", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.set_ == "B" and not frozen_ok():
        print("set B needs eval/FROZEN with matching hashes: run python -m eval.freeze first", file=sys.stderr)
        return 2
    data = args.data if args.data is not None else get_settings().data_dir
    sessions = load_sessions(data, set_=args.set_)
    if not sessions:
        print(f"no labelled set {args.set_} sessions with results")
        return 0
    voting_off = check_ids(args.voting_off)
    suffix = "set A, tuning set" if args.set_ == "A" else "set B"
    blocks = [(f"all ({suffix})", sessions)]
    groups = {
        "device": lambda s: s.label.device,
        "light": lambda s: s.label.light,
        "mode": lambda s: s.mode or "unknown",
    }
    for name, key in groups.items():
        for value in sorted({key(s) for s in sessions}):
            blocks.append((f"{name} {value}", [s for s in sessions if key(s) == value]))
    for title, group in blocks:
        print("\n".join(_lines(title, metrics(group, voting_off))))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
