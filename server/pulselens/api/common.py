"""Request helpers shared by the customer and agent routes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from pulselens.engine.store import SessionStore


def store(request: Request) -> SessionStore:
    return request.app.state.store


def session_or_404(request: Request, session_id: str) -> dict[str, Any]:
    try:
        return store(request).get(session_id)
    except KeyError:
        raise HTTPException(404, "unknown_session") from None
