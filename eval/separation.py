"""Per-check separation (K10a): AUC of risk, genuine vs each attack kind, set A only."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from eval.load import EvalSession, load_sessions
from pulselens.config import get_settings


def auc(genuine: list[float], attack: list[float]) -> float | None:
    """P(random attack score > random genuine score), ties count half (Mann-Whitney); None if either list is empty."""
    if not genuine or not attack:
        return None
    wins = 0.0
    for a in attack:
        for g in genuine:
            wins += 1.0 if a > g else 0.5 if a == g else 0.0
    return wins / (len(genuine) * len(attack))


@dataclass(frozen=True)
class SeparationRow:
    check_id: str
    kind: str
    auc: float | None
    n_genuine: int
    n_attack: int


def _scores(sessions: list[EvalSession]) -> dict[str, list[float]]:
    """check_id -> one score per session: the max usable risk of that check in the session."""
    out: dict[str, list[float]] = {}
    for s in sessions:
        best: dict[str, float] = {}
        for r in s.results:
            if r.status == "usable" and r.risk is not None:
                best[r.check_id] = max(r.risk, best.get(r.check_id, r.risk))
        for cid, risk in best.items():
            out.setdefault(cid, []).append(risk)
    return out


def separation(sessions: list[EvalSession]) -> list[SeparationRow]:
    """One row per (check_id, attack kind): AUC of per-session max usable risk, genuine vs that attack kind."""
    genuine = _scores([s for s in sessions if s.label.kind == "genuine"])
    kinds = sorted({s.label.kind for s in sessions} - {"genuine"})
    attack = {k: _scores([s for s in sessions if s.label.kind == k]) for k in kinds}
    check_ids = sorted({r.check_id for s in sessions for r in s.results})
    rows = []
    for cid in check_ids:
        g = genuine.get(cid, [])
        for k in kinds:
            a = attack[k].get(cid, [])
            rows.append(SeparationRow(cid, k, auc(g, a), len(g), len(a)))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Per-check separation (AUC) on labelled set A sessions.")
    parser.add_argument("--data", type=Path, default=None, help="session data dir (default: settings data_dir)")
    parser.add_argument("--out", type=Path, default=Path("eval/out"), help="output dir for separation.csv")
    args = parser.parse_args(argv)
    data = args.data if args.data is not None else get_settings().data_dir
    rows = separation(load_sessions(data, set_="A"))
    if not rows:
        print("no labelled set A sessions with results")
        return 0
    for r in rows:
        score = "AUC n/a" if r.auc is None else f"AUC {r.auc:.2f}"
        print(f"{r.check_id} vs {r.kind}: {score} (genuine n={r.n_genuine}, {r.kind} n={r.n_attack})")
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "separation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check_id", "kind", "auc", "n_genuine", "n_attack"])
        for r in rows:
            w.writerow([r.check_id, r.kind, "" if r.auc is None else r.auc, r.n_genuine, r.n_attack])
    return 0


if __name__ == "__main__":
    sys.exit(main())
