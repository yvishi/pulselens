"""web/src/contracts.ts mirrors server/pulselens/contracts.py: every model and field name is there (CONTRACT 4)."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from pydantic import BaseModel

from pulselens import contracts

TS = Path(__file__).resolve().parents[3] / "web" / "src" / "contracts.ts"


def _models() -> list[type[BaseModel]]:
    return [
        cls
        for _, cls in inspect.getmembers(contracts, inspect.isclass)
        if issubclass(cls, BaseModel) and cls is not contracts.Model and cls.__module__ == contracts.__name__
    ]


def _ts_blocks(text: str) -> dict[str, str]:
    """`export interface X { ... }` bodies by name, plus `export type X = ...` names with an empty body."""
    blocks = {m.group(1): m.group(2) for m in re.finditer(r"export interface (\w+)\s*\{(.*?)\n\}", text, re.S)}
    for m in re.finditer(r"export type (\w+)\s*=", text):
        blocks.setdefault(m.group(1), "")
    return blocks


def test_every_model_and_field_is_in_ts() -> None:
    blocks = _ts_blocks(TS.read_text(encoding="utf-8"))
    missing = []
    for model in _models():
        body = blocks.get(model.__name__)
        if body is None:
            missing.append(model.__name__)
            continue
        fields = set(re.findall(r"^\s*(\w+)\??:", body, re.M))
        missing += [f"{model.__name__}.{f}" for f in model.model_fields if f not in fields]
    assert not missing, f"missing from contracts.ts: {missing}"


def test_every_literal_alias_is_in_ts() -> None:
    blocks = _ts_blocks(TS.read_text(encoding="utf-8"))
    aliases = ["Mode", "Family", "GateStatus", "Outcome", "StepUp", "SessionState", "CustomerMessage", "AgentAction",
               "Product", "Platform", "FamilyState", "ThresholdSource", "PlotKind", "Step"]
    assert [a for a in aliases if a not in blocks] == []
