"""Customer session API (docs/CONTRACT.md section 2, rows 2 to 8). Agent rows (9 to 12) arrive with K7.

Every customer call checks, in order: the session exists (404), the bearer token (401), expiry (410).
No customer response ever carries a risk, flag, check id, family or outcome.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import TypeAdapter, ValidationError

from pulselens.api.common import session_or_404
from pulselens.api.common import store as _store
from pulselens.contracts import (
    Challenge,
    ChallengeEvent,
    CustomerStatus,
    Decision,
    FrameBatchMeta,
    Plan,
    Preflight,
    SessionCreate,
    SessionCreated,
)
from pulselens.engine.auth import bearer
from pulselens.engine.fusion import customer_message
from pulselens.engine.planner import make_challenge, plan_session, rng_for_nonce
from pulselens.engine.store import FINISHED, FrameCapExceeded

router = APIRouter(prefix="/api")
EVENTS = TypeAdapter(list[ChallengeEvent])
Auth = Annotated[str | None, Header(alias="Authorization")]


def _customer(request: Request, session_id: str, authorization: str | None) -> dict[str, Any]:
    session = session_or_404(request, session_id)
    store = _store(request)
    if not store.signer.check(session_id, bearer(authorization)):
        raise HTTPException(401, "unauthorized")
    if store.effective_state(session) == "expired":
        if session["state"] != "expired":
            store.set_state(session_id, "expired")
        raise HTTPException(410, "session_expired")
    return session


def _refuse_after_complete(request: Request, session: dict[str, Any]) -> None:
    """Refuses frames and events after /complete, and counts the attempt (K5: integrity.after_complete)."""
    if session["state"] in FINISHED:
        _store(request).increment(session["session_id"], "after_complete_attempts")
        raise HTTPException(409, "session_complete")


@router.post("/sessions", status_code=201)
def create_session(request: Request, body: SessionCreate) -> SessionCreated:
    try:
        return _store(request).create(body)
    except KeyError:
        raise HTTPException(404, "unknown_previous_session") from None


@router.post("/sessions/{session_id}/preflight")
def preflight(request: Request, session_id: str, body: Preflight, authorization: Auth = None) -> Plan:
    session = _customer(request, session_id, authorization)
    store = _store(request)
    if store.has(session_id, "challenge"):
        raise HTTPException(409, "challenge_already_issued")
    plan = plan_session(body, bool(session["no_flash"]), request.app.state.config)
    store.save_model(session_id, "preflight", body)
    store.save_model(session_id, "plan", plan)
    store.set_state(session_id, "preflight")
    return plan


@router.get("/sessions/{session_id}/challenge")
def challenge(request: Request, session_id: str, authorization: Auth = None) -> Challenge:
    session = _customer(request, session_id, authorization)
    store = _store(request)
    raw_plan = store.load(session_id, "plan")
    if raw_plan is None:
        raise HTTPException(409, "no_plan")
    nonce = session["nonce"]
    issued = make_challenge(Plan.model_validate(raw_plan), session_id, nonce, rng_for_nonce(nonce),
                            request.app.state.config)
    if not store.issue_challenge(session_id, issued):  # single use, even under concurrent requests
        raise HTTPException(409, "challenge_already_issued")
    return issued


async def _read_batch(request: Request, limits: dict[str, Any]) -> tuple[FrameBatchMeta, list[bytes]]:
    async with request.form(max_files=1000, max_fields=10) as form:
        try:
            meta = FrameBatchMeta.model_validate(json.loads(str(form.get("meta") or "")))
        except (json.JSONDecodeError, ValidationError):
            raise HTTPException(422, "bad_frame_meta") from None
        if len(meta.frames) > limits["max_batch_frames"]:
            raise HTTPException(413, "too_many_frames_in_batch")
        jpegs = []
        for frame in meta.frames:
            part = form.get(f"f{frame.idx}")
            if part is None or not hasattr(part, "read"):
                raise HTTPException(422, f"missing_frame_part_f{frame.idx}")
            data = await part.read()
            if len(data) > limits["max_jpeg_kb"] * 1024:
                raise HTTPException(413, "jpeg_too_large")
            jpegs.append(data)
    return meta, jpegs


@router.post("/sessions/{session_id}/frames", status_code=204)
async def frames(request: Request, session_id: str, authorization: Auth = None) -> Response:
    session = _customer(request, session_id, authorization)
    limits = request.app.state.config["session"]
    store = _store(request)
    if session["state"] in FINISHED:
        # Still 409, but an exact re-send of a stored batch (a retry whose response was lost) is a network
        # artefact, not a late frame, so it does not count toward integrity.after_complete (AGENTS.md rule 3).
        try:
            meta, jpegs = await _read_batch(request, limits)
        except HTTPException:
            meta, jpegs = None, []
        with store.lock(session_id):
            if meta is None or not store.is_resend(session_id, meta, jpegs):
                store.increment(session_id, "after_complete_attempts")
        raise HTTPException(409, "session_complete")
    meta, jpegs = await _read_batch(request, limits)
    try:
        store.append_frames(session_id, meta, jpegs, max_frames=limits["max_frames"])
    except FrameCapExceeded:
        raise HTTPException(413, "too_many_frames_in_session") from None
    return Response(status_code=204)


@router.post("/sessions/{session_id}/events", status_code=204)
async def events(request: Request, session_id: str, authorization: Auth = None) -> Response:
    session = _customer(request, session_id, authorization)
    _refuse_after_complete(request, session)
    try:
        parsed = EVENTS.validate_json(await request.body())
    except ValidationError:
        raise HTTPException(422, "bad_events") from None
    _store(request).append_events(session_id, parsed)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/complete", status_code=202)
def complete(request: Request, session_id: str, authorization: Auth = None) -> Response:
    session = _customer(request, session_id, authorization)
    if session["state"] in FINISHED:
        raise HTTPException(409, "already_complete")
    store = _store(request)
    store.update(session_id, state="analysing", completed_at_ms=int(store.clock()))
    runner = request.app.state.runner
    if runner is not None:
        request.app.state.executor.submit(runner, store.path(session_id), store)
    return Response(status_code=202)


@router.get("/sessions/{session_id}/status")
def status(request: Request, session_id: str, authorization: Auth = None) -> CustomerStatus:
    session = _customer(request, session_id, authorization)
    raw = _store(request).load(session_id, "decision")
    return customer_message(session["state"], Decision.model_validate(raw) if raw else None)
