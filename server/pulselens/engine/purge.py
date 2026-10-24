"""Purge sweep: demo sessions by age, labelled sessions after the event; never touches unreadable or analysing ones."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def purge(data_dir: Path, *, now_ms: float, max_age_ms: int = 3_600_000, labelled: bool = False) -> list[str]:
    """Deletes session folders and returns their ids. labelled=False removes unlabelled sessions older than
    max_age_ms; labelled=True removes every labelled session. A folder with a missing or invalid session.json, or
    in state "analysing", is always kept, and one failing folder never stops the sweep."""
    deleted: list[str] = []
    try:
        folders = sorted(p for p in Path(data_dir).iterdir() if p.is_dir())
    except OSError:
        return deleted
    for folder in folders:
        try:
            session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
            if session.get("state") == "analysing":
                continue
            if labelled:
                doomed = session.get("label") is not None
            else:
                doomed = session.get("label") is None and now_ms - session["created_at_ms"] > max_age_ms
            if doomed:
                shutil.rmtree(folder)
                deleted.append(folder.name)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return deleted
