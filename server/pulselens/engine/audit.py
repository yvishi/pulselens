"""Hash-chained evidence record (docs/tasks/keshav.md K8): one line per event in session_dir/audit.jsonl.

The caller holds the session lock (store.lock); this module adds no locking.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

GENESIS = "0" * 64


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _last_state(path: Path) -> tuple[int, str]:
    """Return (number of existing lines, hash of the last line or GENESIS)."""
    if not path.exists():
        return 0, GENESIS
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return 0, GENESIS
    return len(lines), json.loads(lines[-1])["hash"]


def append(session_dir: Path, event_type: str, payload: bytes | dict) -> str:
    """Append one event to the chain and return its hash."""
    path = session_dir / "audit.jsonl"
    seq, prev_hash = _last_state(path)
    data = payload if isinstance(payload, bytes) else canonical_json(payload).encode()
    line: dict[str, object] = {
        "seq": seq,
        "at_ms": int(time.time() * 1000),
        "type": event_type,
        "payload_sha256": _sha256(data),
        "prev_hash": prev_hash,
    }
    line["hash"] = _line_hash(line)
    with path.open("a", encoding="utf-8") as f:
        f.write(canonical_json(line) + "\n")
    return str(line["hash"])


def _line_hash(line_without_hash: dict) -> str:
    """sha256(prev_hash + canonical_json(line without "hash")); the line carries its own prev_hash."""
    return _sha256((str(line_without_hash["prev_hash"]) + canonical_json(line_without_hash)).encode())


def verify(session_dir: Path) -> tuple[bool, int | None]:
    """Return (True, None) if the whole chain is intact, else (False, first bad line number, 1-based)."""
    path = session_dir / "audit.jsonl"
    if not path.exists():
        return True, None
    prev_hash = GENESIS
    for i, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        try:
            line = json.loads(raw)
            body = {k: v for k, v in line.items() if k != "hash"}
            good = (
                type(line["seq"]) is int
                and line["seq"] == i - 1
                and line["prev_hash"] == prev_hash
                and line["hash"] == _line_hash(body)
            )
        except (ValueError, KeyError, AttributeError, TypeError):
            good = False
        if not good:
            return False, i
        prev_hash = line["hash"]
    return True, None
