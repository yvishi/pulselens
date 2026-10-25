"""Agent API (docs/CONTRACT.md section 2, rows 9 to 12): the console's view of sessions. Header X-Agent-Passcode.

The agent decides; these routes only show evidence and record what the agent chose.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse

from pulselens.api.common import session_or_404, store
from pulselens.bundle import frame_name, load_bundle
from pulselens.contracts import AgentDecision, SessionReport, SessionSummary
from pulselens.engine.auth import passcode_ok
from pulselens.engine.store import AlreadyDecided

router = APIRouter(prefix="/api")
Passcode = Annotated[str | None, Header(alias="X-Agent-Passcode")]


def _agent(request: Request, passcode: str | None) -> None:
    if not passcode_ok(passcode, request.app.state.settings.agent_passcode):
        raise HTTPException(401, "unauthorized")


@router.get("/sessions")
def list_sessions(request: Request, x_agent_passcode: Passcode = None) -> list[SessionSummary]:
    _agent(request, x_agent_passcode)
    return store(request).list()


@router.get("/sessions/{session_id}/result")
def result(request: Request, session_id: str, x_agent_passcode: Passcode = None) -> SessionReport:
    _agent(request, x_agent_passcode)
    session = session_or_404(request, session_id)
    s = store(request)
    bundle = load_bundle(s.path(session_id))
    return SessionReport(
        session_id=session_id,
        product=session["product"],
        attempt=session["attempt"],
        state=s.effective_state(session),
        label=bundle.label,
        preflight=bundle.preflight,
        plan=bundle.plan,
        challenge=bundle.challenge,
        events=bundle.events,
        frame_count=s.frame_count(session_id),
        results=bundle.results,
        decision=bundle.decision,
        agent_decision=bundle.agent_decision,
    )


@router.get("/sessions/{session_id}/frames/{idx}.jpg")
def frame(request: Request, session_id: str, idx: int, x_agent_passcode: Passcode = None) -> FileResponse:
    _agent(request, x_agent_passcode)
    session_or_404(request, session_id)
    path = store(request).path(session_id) / "frames" / frame_name(idx)
    if idx < 0 or not path.exists():
        raise HTTPException(404, "unknown_frame")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/sessions/{session_id}/agent", status_code=204)
def agent_decision(request: Request, session_id: str, body: AgentDecision,
                   x_agent_passcode: Passcode = None) -> Response:
    """Records the agent's action as agent.json, stamped with when it was taken (also in the audit log, K8).

    Approve and escalate are final: once either is recorded, any later action gets 409. Re-verify is not final.
    """
    _agent(request, x_agent_passcode)
    session_or_404(request, session_id)
    s = store(request)
    if not s.has(session_id, "decision"):
        raise HTTPException(409, "no_decision_yet")
    try:
        s.record_agent(session_id, body)
    except AlreadyDecided:
        raise HTTPException(409, "already_decided") from None
    return Response(status_code=204)
