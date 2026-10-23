"""Load labelled, analysed session bundles (results.json plus optional decision.json) from a data directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult, Decision, Label, Mode

_RESULTS = TypeAdapter(list[CheckResult])


@dataclass(frozen=True)
class EvalSession:
    session_id: str
    label: Label
    mode: Mode | None
    results: list[CheckResult]
    decision: Decision | None
    completed_at_ms: int | None


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
        try:
            results = _RESULTS.validate_json((path / "results.json").read_bytes())
            decision_path = path / "decision.json"
            decision = Decision.model_validate_json(decision_path.read_bytes()) if decision_path.exists() else None
        except (OSError, ValidationError, json.JSONDecodeError):
            continue
        sessions.append(EvalSession(
            session_id=path.name, label=bundle.label, mode=bundle.plan.mode if bundle.plan else None,
            results=results, decision=decision, completed_at_ms=bundle.session.get("completed_at_ms")))
    return sessions
