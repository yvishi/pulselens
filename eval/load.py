"""Load labelled, analysed session bundles (results.json plus optional decision.json) from a data directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult, Decision, Label, Mode, Plan


@dataclass(frozen=True)
class EvalSession:
    session_id: str
    label: Label
    mode: Mode | None
    results: list[CheckResult]
    decision: Decision | None
    completed_at_ms: int | None
    plan: Plan | None = None  # fusion needs the mode and the attempt to re-fuse (eval/run.py)
    attempt: int = 1


def load_sessions(data_dir: Path, set_: Literal["A", "B"] | None = None) -> list[EvalSession]:
    """Sessions under data_dir that have a label and a results.json, sorted by id; unreadable folders are skipped."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    sessions = []
    for path in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        bundle = load_bundle(path)
        if bundle.label is None or (set_ is not None and bundle.label.set != set_):
            continue
        if not bundle.results or ((path / "decision.json").exists() and bundle.decision is None):
            continue  # not analysed, or an unreadable results.json / decision.json
        sessions.append(EvalSession(
            session_id=path.name, label=bundle.label, mode=bundle.plan.mode if bundle.plan else None,
            results=bundle.results, decision=bundle.decision, completed_at_ms=bundle.session.get("completed_at_ms"),
            plan=bundle.plan, attempt=int(bundle.session.get("attempt", 1))))
    return sessions
