"""Session bundle on disk (docs/CONTRACT.md section 5): the engine writes it, the analysis reads it.

`load_bundle` never raises on a missing optional file, and skips lines it cannot parse instead of losing the session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from pulselens.contracts import Challenge, ChallengeEvent, FrameMeta, Label, Plan, Preflight

if TYPE_CHECKING:
    import numpy as np

FRAME_FIELDS = set(FrameMeta.model_fields)


def frame_name(idx: int) -> str:
    return f"{idx:06d}.jpg"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Rows that parse to a JSON object, and how many lines did not."""
    if not path.exists():
        return [], 0
    rows, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            bad += 1
    return rows, bad


def _model(cls: type[BaseModel], data: Any) -> Any:
    if data is None:
        return None
    try:
        return cls.model_validate(data)
    except ValidationError:
        return None


@dataclass
class Bundle:
    path: Path
    session: dict
    preflight: Preflight | None
    plan: Plan | None
    challenge: Challenge | None
    frames: list[FrameMeta]  # sorted by idx
    events: list[ChallengeEvent]
    label: Label | None
    skipped_lines: int = field(default=0)  # unreadable lines in frames.jsonl and events.jsonl

    def frame_path(self, idx: int) -> Path:
        return self.path / "frames" / frame_name(idx)

    def read_frame(self, idx: int) -> np.ndarray | None:
        """BGR uint8 via cv2.imdecode; None if the file is missing or corrupt. Imports cv2 lazily."""
        try:
            data = self.frame_path(idx).read_bytes()
        except OSError:
            return None
        if not data:  # cv2.imdecode asserts on an empty buffer instead of returning None
            return None
        import cv2
        import numpy as np

        try:
            img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            return None
        return img if img is not None and img.ndim == 3 else None


def load_bundle(path: Path) -> Bundle:
    path = Path(path)
    session = _read_json(path / "session.json") or {}
    frame_rows, bad_frames = _read_jsonl(path / "frames.jsonl")
    event_rows, bad_events = _read_jsonl(path / "events.jsonl")
    frames: dict[int, FrameMeta] = {}
    skipped = bad_frames + bad_events
    for row in frame_rows:  # extra keys (batch_seq, received_at_ms) are engine bookkeeping, not part of FrameMeta
        meta = _model(FrameMeta, {k: v for k, v in row.items() if k in FRAME_FIELDS})
        if meta is None:
            skipped += 1
        else:
            frames.setdefault(meta.idx, meta)
    events = []
    for row in event_rows:
        event = _model(ChallengeEvent, row)
        if event is None:
            skipped += 1
        else:
            events.append(event)
    return Bundle(
        path=path,
        session=session,
        preflight=_model(Preflight, _read_json(path / "preflight.json")),
        plan=_model(Plan, _read_json(path / "plan.json")),
        challenge=_model(Challenge, _read_json(path / "challenge.json")),
        frames=[frames[i] for i in sorted(frames)],
        events=events,
        label=_model(Label, session.get("label")),
        skipped_lines=skipped,
    )


def write_bundle(
    path: Path,
    *,
    session: dict,
    preflight: Preflight | None,
    plan: Plan | None,
    challenge: Challenge | None,
    frames: list[tuple[FrameMeta, bytes]],
    events: list[ChallengeEvent],
) -> None:
    """Writes a complete bundle in one go: for tests and synthetic fixtures."""
    path = Path(path)
    (path / "frames").mkdir(parents=True, exist_ok=True)
    (path / "session.json").write_text(json.dumps(session), encoding="utf-8")
    for name, model in (("preflight", preflight), ("plan", plan), ("challenge", challenge)):
        if model is not None:
            (path / f"{name}.json").write_text(model.model_dump_json(), encoding="utf-8")
    lines = []
    for meta, jpeg in frames:
        (path / "frames" / frame_name(meta.idx)).write_bytes(jpeg)
        lines.append(meta.model_dump_json())
    (path / "frames.jsonl").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    (path / "events.jsonl").write_text("".join(f"{e.model_dump_json()}\n" for e in events), encoding="utf-8")
