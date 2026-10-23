"""Session storage (docs/CONTRACT.md section 5): one folder per session, one lock per session for every write."""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from pulselens.bundle import frame_name
from pulselens.contracts import (
    ChallengeEvent,
    Decision,
    FrameBatchMeta,
    Mode,
    Plan,
    SessionCreate,
    SessionCreated,
    SessionState,
    SessionSummary,
)
from pulselens.engine.auth import TokenSigner

Clock = Callable[[], float]  # wall-clock milliseconds
FINISHED: tuple[SessionState, ...] = ("analysing", "done")  # past /complete: never expires


def _wall_ms() -> float:
    return time.time() * 1000


class SessionStore:
    def __init__(
        self, root: Path, *, signer: TokenSigner | None = None, ttl_min: float = 15, clock: Clock = _wall_ms
    ) -> None:
        self.root = Path(root)
        self.signer = signer or TokenSigner()
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_ms = ttl_min * 60_000
        self.clock = clock
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    # --- paths and locks ---

    def path(self, session_id: str) -> Path:
        if not session_id.isalnum():  # session ids are hex; anything else could escape the data dir
            raise KeyError(session_id)
        return self.root / session_id

    def lock(self, session_id: str) -> threading.RLock:
        """Every read and write of a session's files takes this lock. Re-entrant, and it also keeps Windows from
        refusing an atomic replace of session.json while another thread has it open."""
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.RLock())

    # --- session.json ---

    def create(self, body: SessionCreate) -> SessionCreated:
        """Writes session.json. A retry (previous_session_id) is attempt previous + 1; raises KeyError when the
        previous session is unknown."""
        attempt = self.get(body.previous_session_id)["attempt"] + 1 if body.previous_session_id else 1
        session_id = secrets.token_hex(8)
        created = int(self.clock())
        session = {
            "session_id": session_id,
            "nonce": secrets.token_hex(16),
            "product": body.product,
            "no_flash": body.no_flash,
            "attempt": attempt,
            "previous_session_id": body.previous_session_id,
            "created_at_ms": created,
            "expires_at_ms": created + int(self.ttl_ms),
            "state": "created",
            "label": body.label.model_dump() if body.label else None,
        }
        folder = self.path(session_id)
        (folder / "frames").mkdir(parents=True)
        with self.lock(session_id):
            self._write_json(folder / "session.json", session)
        token = self.signer.customer_token(session_id)
        return SessionCreated(
            session_id=session_id,
            nonce=session["nonce"],
            customer_token=token,
            customer_url=f"/customer/{session_id}?t={token}",
            attempt=attempt,
            expires_at_ms=session["expires_at_ms"],
        )

    def get(self, session_id: str) -> dict[str, Any]:
        """session.json; raises KeyError for an unknown session."""
        path = self.path(session_id) / "session.json"
        if not path.exists():
            raise KeyError(session_id)
        with self.lock(session_id):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise KeyError(session_id) from None

    def update(self, session_id: str, **patch: Any) -> dict[str, Any]:
        with self.lock(session_id):
            session = {**self.get(session_id), **patch}
            self._write_json(self.path(session_id) / "session.json", session)
            return session

    def increment(self, session_id: str, key: str) -> int:
        """Adds one to a counter in session.json (e.g. after_complete_attempts) and returns the new value."""
        with self.lock(session_id):
            session = self.get(session_id)
            session[key] = int(session.get(key, 0)) + 1
            self._write_json(self.path(session_id) / "session.json", session)
            return session[key]

    def set_state(self, session_id: str, state: SessionState) -> None:
        self.update(session_id, state=state)

    def effective_state(self, session: dict[str, Any]) -> SessionState:
        """The state every reader sees: an unfinished session past its TTL is expired, even before it is saved so."""
        if session["state"] not in FINISHED and self.clock() >= session["expires_at_ms"]:
            return "expired"
        return session["state"]

    # --- bundle files ---

    def save_model(self, session_id: str, name: str, model: BaseModel) -> None:
        """e.g. name "plan" → plan.json."""
        with self.lock(session_id):
            (self.path(session_id) / f"{name}.json").write_text(model.model_dump_json(), encoding="utf-8")

    def save_once(self, session_id: str, name: str, model: BaseModel) -> bool:
        """Writes name.json only if it does not exist yet (single use under concurrency). False if it existed."""
        with self.lock(session_id):
            if self.has(session_id, name):
                return False
            self.save_model(session_id, name, model)
            return True

    def has(self, session_id: str, name: str) -> bool:
        return (self.path(session_id) / f"{name}.json").exists()

    def load(self, session_id: str, name: str) -> Any:
        """name.json parsed, or None when it is missing or unreadable."""
        with self.lock(session_id):
            try:
                return json.loads((self.path(session_id) / f"{name}.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None

    def frame_count(self, session_id: str) -> int:
        return len(list((self.path(session_id) / "frames").glob("*.jpg")))

    def append_frames(self, session_id: str, meta: FrameBatchMeta, jpegs: list[bytes]) -> None:
        """JPEGs exactly as uploaded, plus one frames.jsonl line each with batch_seq and received_at_ms.
        A repeated idx keeps the first JPEG; its meta line is still appended, so integrity (K5) can see it."""
        folder = self.path(session_id)
        received = int(self.clock())
        with self.lock(session_id):
            lines = []
            for frame, jpeg in zip(meta.frames, jpegs, strict=True):
                target = folder / "frames" / frame_name(frame.idx)
                if not target.exists():
                    target.write_bytes(jpeg)
                lines.append({**frame.model_dump(), "batch_seq": meta.batch_seq, "received_at_ms": received})
            with (folder / "frames.jsonl").open("a", encoding="utf-8") as f:
                f.writelines(json.dumps(line) + "\n" for line in lines)

    def append_events(self, session_id: str, events: list[ChallengeEvent]) -> None:
        with self.lock(session_id), (self.path(session_id) / "events.jsonl").open("a", encoding="utf-8") as f:
            f.writelines(e.model_dump_json() + "\n" for e in events)

    # --- listing ---

    def list(self) -> list[SessionSummary]:
        """Every session, newest first."""
        out = []
        for folder in self.root.iterdir():
            try:
                s = self.get(folder.name)
            except KeyError:
                continue
            plan = self.load(folder.name, "plan")
            decision = self.load(folder.name, "decision")
            mode: Mode | None = Plan.model_validate(plan).mode if plan else None
            outcome = Decision.model_validate(decision).outcome if decision else None
            out.append(
                SessionSummary(
                    session_id=s["session_id"],
                    created_at_ms=s["created_at_ms"],
                    product=s["product"],
                    attempt=s["attempt"],
                    state=self.effective_state(s),
                    mode=mode,
                    outcome=outcome,
                    label_kind=(s.get("label") or {}).get("kind"),
                )
            )
        return sorted(out, key=lambda x: x.created_at_ms, reverse=True)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
