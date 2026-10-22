"""Agent API (docs/CONTRACT.md section 2, rows 9 to 12): the console's view of sessions. Header X-Agent-Passcode.

The agent decides; these routes only show evidence and record what the agent chose.
"""

from __future__ import annotations

import json
import time
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import TypeAdapter, ValidationError

from pulselens.bundle import frame_name, load_bundle
from pulselens.contracts import AgentDecision, CheckResult, Decision, SessionReport, SessionSummary
from pulselens.engine.auth import passcode_ok
from pulselens.engine.store import SessionStore

router = APIRouter(prefix="/api")
RESULTS = TypeAdapter(list[CheckResult])
Passcode = Annotated[str | None, Header(alias="X-Agent-Passcode")]


def _store(request: Request) -> SessionStore:
    return request.app.state.store


def _agent(request: Request, passcode: str | None) -> None:
    if not passcode_ok(passcode, request.app.state.settings.agent_passcode):
        raise HTTPException(401, "unauthorized")


def _session(request: Request, session_id: str) -> dict[str, Any]:
    try:
        return _store(request).get(session_id)
    except KeyError:
        raise HTTPException(404, "unknown_session") from None


@router.get("/sessions")
def list_sessions(request: Request, x_agent_passcode: Passcode = None) -> list[SessionSummary]:
    _agent(request, x_agent_passcode)
    return _store(request).list()


@router.get("/sessions/{session_id}/result")
def result(request: Request, session_id: str, x_agent_passcode: Passcode = None) -> SessionReport:
    _agent(request, x_agent_passcode)
    session = _session(request, session_id)
    store = _store(request)
    bundle = load_bundle(store.path(session_id))
    try:
        results = RESULTS.validate_python(store.load_json(session_id, "results.json") or [])
    except ValidationError:
        results = []
    raw_decision = store.load_json(session_id, "decision.json")
    raw_agent = store.load_json(session_id, "agent.json")
    state = session["state"]
    if state not in ("analysing", "done") and store.expired(session):
        state = "expired"
    return SessionReport(
        session_id=session_id,
        product=session["product"],
        attempt=session["attempt"],
        state=state,
        label=bundle.label,
        preflight=bundle.preflight,
        plan=bundle.plan,
        challenge=bundle.challenge,
        events=bundle.events,
        frame_count=store.frame_count(session_id),
        results=results,
        decision=Decision.model_validate(raw_decision) if raw_decision else None,
        agent_decision=AgentDecision.model_validate(
            {k: v for k, v in raw_agent.items() if k in AgentDecision.model_fields}) if raw_agent else None,
    )


@router.get("/sessions/{session_id}/frames/{idx}.jpg")
def frame(request: Request, session_id: str, idx: int, x_agent_passcode: Passcode = None) -> FileResponse:
    _agent(request, x_agent_passcode)
    _session(request, session_id)
    path = _store(request).path(session_id) / "frames" / frame_name(idx)
    if idx < 0 or not path.exists():
        raise HTTPException(404, "unknown_frame")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/sessions/{session_id}/agent", status_code=204)
def agent_decision(request: Request, session_id: str, body: AgentDecision,
                   x_agent_passcode: Passcode = None) -> Response:
    """Records the agent's action. `agent.json` also keeps when it was taken (`at_ms`), for the console."""
    _agent(request, x_agent_passcode)
    _session(request, session_id)
    store = _store(request)
    if store.load_json(session_id, "decision.json") is None:
        raise HTTPException(409, "no_decision_yet")
    payload = {**body.model_dump(), "at_ms": int(time.time() * 1000)}
    with store.lock(session_id):
        (store.path(session_id) / "agent.json").write_text(json.dumps(payload), encoding="utf-8")
    return Response(status_code=204)
