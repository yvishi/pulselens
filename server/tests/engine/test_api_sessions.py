"""K2: the customer session API (docs/CONTRACT.md section 2, rows 2 to 8)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.bundle import load_bundle
from pulselens.config import Settings
from pulselens.contracts import Decision, FamilySummary, Plan
from pulselens.engine.fusion import fuse
from pulselens.engine.integrity import check_integrity
from pulselens.engine.store import SessionStore

FORBIDDEN = ("risk", "flag", "check_id", "family", "outcome")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


class Clock:
    def __init__(self) -> None:
        self.ms = 1_800_000_000_000.0

    def __call__(self) -> float:
        return self.ms


def fake_runner(session_dir: Path, store: SessionStore) -> None:
    """Stands in for K4: a PASS decision, then state done."""
    families = [FamilySummary(family=f, state="not_raised", usable_checks=1, flagged_checks=0, reasons=[])
                for f in "ABCD"]
    decision = Decision(outcome="PASS", step_up=None, families=families, reasons=["FAKE ANALYSIS"],
                        integrity_violation=False, provisional=True, decided_at_ms=int(time.time() * 1000))
    (session_dir / "decision.json").write_text(decision.model_dump_json(), encoding="utf-8")
    store.set_state(session_dir.name, "done")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(tmp_path: Path, clock: Clock) -> TestClient:
    settings = Settings(agent_passcode="pc", data_dir=tmp_path / "data", fake_analysis=True)
    with TestClient(create_app(settings, runner=fake_runner, clock=clock)) as c:
        yield c


def preflight(**over) -> dict:
    return {
        "user_agent": "test", "platform": "desktop", "browser": "Brave 155", "camera_label": "cam", "width": 640,
        "height": 480, "measured_fps": 30.0, "dropped_frame_ratio": 0.0, "blur": 100.0, "brightness": 120.0,
        "face_found": True, "face_fraction": 0.1, "controls": [], "gyro": False, "no_flash_requested": False,
        "clock": "captureTime", "probe": [], **over,
    }


def create(client: TestClient, **body) -> dict:
    r = client.post("/api/sessions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def auth(s: dict) -> dict:
    return {"Authorization": f"Bearer {s['customer_token']}"}


def post_frames(client: TestClient, s: dict, idxs: list[int], seq: int = 0, jpeg: bytes = JPEG, shift: float = 0.0):
    meta = {"batch_seq": seq, "frames": [{"idx": i, "t_ms": 33.3 * i + shift, "w": 640, "h": 480} for i in idxs]}
    files = {f"f{i}": (f"{i}.jpg", jpeg, "image/jpeg") for i in idxs}
    return client.post(f"/api/sessions/{s['session_id']}/frames", headers=auth(s), data={"meta": json.dumps(meta)},
                       files=files)


def ready(client: TestClient, s: dict) -> dict:
    """Preflight and challenge done: the session is capturing."""
    sid = s["session_id"]
    assert client.post(f"/api/sessions/{sid}/preflight", headers=auth(s), json=preflight()).status_code == 200
    r = client.get(f"/api/sessions/{sid}/challenge", headers=auth(s))
    assert r.status_code == 200, r.text
    return r.json()


def test_create_returns_tokens_and_url(client: TestClient) -> None:
    s = create(client)
    assert s["customer_url"] == f"/customer/{s['session_id']}?t={s['customer_token']}"
    assert s["attempt"] == 1 and len(s["nonce"]) == 32 and len(s["customer_token"]) == 32


def test_previous_session_sets_attempt(client: TestClient) -> None:
    first = create(client)
    second = create(client, previous_session_id=first["session_id"])
    third = create(client, previous_session_id=second["session_id"])
    assert (second["attempt"], third["attempt"]) == (2, 3)
    assert client.post("/api/sessions", json={"previous_session_id": "0" * 16}).status_code == 404


def test_customer_auth_required(client: TestClient) -> None:
    s = create(client)
    url = f"/api/sessions/{s['session_id']}/preflight"
    assert client.post(url, json=preflight()).status_code == 401
    r = client.post(url, headers={"Authorization": "Bearer wrong"}, json=preflight())
    assert r.status_code == 401 and r.json() == {"detail": "unauthorized"}
    other = create(client)  # another session's token is wrong too
    assert client.post(url, headers=auth(other), json=preflight()).status_code == 401


def test_unknown_session_and_path_tricks_are_404(client: TestClient) -> None:
    for sid in ("0" * 16, "..", "%2e%2e", "abc.def"):
        r = client.get(f"/api/sessions/{sid}/status", headers={"Authorization": "Bearer x"})
        assert r.status_code == 404, sid


def test_preflight_returns_the_plan_and_saves_it(client: TestClient) -> None:
    s = create(client)
    r = client.post(f"/api/sessions/{s['session_id']}/preflight", headers=auth(s), json=preflight(measured_fps=10.4))
    assert r.json()["mode"] == "CONSTRAINED" and r.json()["reasons"] == ["mode.constrained.fps_too_low_for_light"]
    no_flash = create(client, no_flash=True)
    r = client.post(f"/api/sessions/{no_flash['session_id']}/preflight", headers=auth(no_flash), json=preflight())
    assert r.json()["mode"] == "NO_FLASH"


def test_challenge_is_single_use(client: TestClient) -> None:
    s = create(client)
    first = ready(client, s)
    assert first["nonce"] == s["nonce"] and first["session_id"] == s["session_id"]
    r = client.get(f"/api/sessions/{s['session_id']}/challenge", headers=auth(s))
    assert r.status_code == 409 and r.json()["detail"] == "challenge_already_issued"
    # Preflight cannot re-plan after the challenge went out.
    r = client.post(f"/api/sessions/{s['session_id']}/preflight", headers=auth(s), json=preflight())
    assert r.status_code == 409


def test_challenge_is_single_use_under_concurrency(client: TestClient) -> None:
    s = create(client)
    client.post(f"/api/sessions/{s['session_id']}/preflight", headers=auth(s), json=preflight())
    codes: list[int] = []
    threads = [threading.Thread(target=lambda: codes.append(
        client.get(f"/api/sessions/{s['session_id']}/challenge", headers=auth(s)).status_code)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200] + [409] * 7


def test_challenge_before_preflight(client: TestClient) -> None:
    s = create(client)
    r = client.get(f"/api/sessions/{s['session_id']}/challenge", headers=auth(s))
    assert r.status_code == 409 and r.json()["detail"] == "no_plan"


def test_frames_written(client: TestClient, tmp_path: Path) -> None:
    s = create(client)
    ready(client, s)
    assert post_frames(client, s, [0, 1, 2]).status_code == 204
    folder = tmp_path / "data" / s["session_id"]
    assert sorted(p.name for p in (folder / "frames").iterdir()) == ["000000.jpg", "000001.jpg", "000002.jpg"]
    assert (folder / "frames" / "000001.jpg").read_bytes() == JPEG
    lines = [json.loads(line) for line in (folder / "frames.jsonl").read_text().splitlines()]
    assert len(lines) == 3 and {line["batch_seq"] for line in lines} == {0} and "received_at_ms" in lines[0]


def test_limits(client: TestClient) -> None:
    s = create(client)
    ready(client, s)
    assert post_frames(client, s, list(range(31))).status_code == 413
    assert post_frames(client, s, [0], jpeg=b"\xff" * (201 * 1024)).status_code == 413
    for seq in range(30):  # 900 frames fit exactly
        assert post_frames(client, s, list(range(seq * 30, seq * 30 + 30)), seq=seq).status_code == 204
    assert post_frames(client, s, [900], seq=30).status_code == 413


def test_frame_parts_must_match_the_meta(client: TestClient) -> None:
    s = create(client)
    ready(client, s)
    meta = {"batch_seq": 0, "frames": [{"idx": 0, "t_ms": 0, "w": 640, "h": 480}]}
    r = client.post(f"/api/sessions/{s['session_id']}/frames", headers=auth(s), data={"meta": json.dumps(meta)},
                    files={"f9": ("9.jpg", JPEG, "image/jpeg")})
    assert r.status_code == 422
    r = client.post(f"/api/sessions/{s['session_id']}/frames", headers=auth(s), data={"meta": "{not json"})
    assert r.status_code == 422


def test_events_appended(client: TestClient, tmp_path: Path) -> None:
    s = create(client)
    ready(client, s)
    ev = [{"step_id": "c0", "status": "shown", "painted_t_ms": 1510.0, "ended_t_ms": 1910.0,
           "shown_rgb": [0.6, 0.5, 0.3]}]
    assert client.post(f"/api/sessions/{s['session_id']}/events", headers=auth(s), json=ev).status_code == 204
    assert client.post(f"/api/sessions/{s['session_id']}/events", headers=auth(s), json=[{"x": 1}]).status_code == 422
    assert len((tmp_path / "data" / s["session_id"] / "events.jsonl").read_text().splitlines()) == 1


def test_frames_after_complete(client: TestClient, tmp_path: Path) -> None:
    s = create(client)
    ready(client, s)
    assert client.post(f"/api/sessions/{s['session_id']}/complete", headers=auth(s)).status_code == 202
    assert post_frames(client, s, [0]).status_code == 409
    assert client.post(f"/api/sessions/{s['session_id']}/events", headers=auth(s), json=[]).status_code == 409
    assert client.post(f"/api/sessions/{s['session_id']}/complete", headers=auth(s)).status_code == 409
    session = json.loads((tmp_path / "data" / s["session_id"] / "session.json").read_text())
    assert session["after_complete_attempts"] == 2  # recorded for integrity.after_complete (K5)


def rows(tmp_path: Path, s: dict) -> list[dict]:
    text = (tmp_path / "data" / s["session_id"] / "frames.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines()]


def protocol_of(tmp_path: Path, s: dict):
    return check_integrity(load_bundle(tmp_path / "data" / s["session_id"]))[0]


def test_exact_resend_is_an_idempotent_no_op(client: TestClient, tmp_path: Path, clock: Clock) -> None:
    # Weak network: the batch was stored but the 204 was lost, so the uploader (Y4) sends it again.
    s = create(client)
    ready(client, s)
    assert post_frames(client, s, list(range(30)), seq=0).status_code == 204
    clock.ms += 500
    assert post_frames(client, s, list(range(30)), seq=0).status_code == 204
    assert post_frames(client, s, list(range(30, 60)), seq=1).status_code == 204
    assert post_frames(client, s, list(range(30, 60)), seq=1).status_code == 204
    idxs = [r["idx"] for r in rows(tmp_path, s)]
    assert idxs == list(range(60))  # each idx once
    protocol = protocol_of(tmp_path, s)
    assert protocol.status != "protocol_error" and "integrity.duplicate_index" not in protocol.reason_codes
    plan = Plan.model_validate(json.loads((tmp_path / "data" / s["session_id"] / "plan.json").read_text()))
    decision = fuse([protocol], plan, 1)
    assert not decision.integrity_violation and "fusion.integrity_violation" not in decision.reasons


def test_resends_do_not_eat_into_the_frame_cap(client: TestClient) -> None:
    s = create(client)
    ready(client, s)
    for seq in range(30):
        assert post_frames(client, s, list(range(seq * 30, seq * 30 + 30)), seq=seq).status_code == 204
    assert post_frames(client, s, list(range(870, 900)), seq=29).status_code == 204  # re-send at the cap: no-op


def test_reused_idx_with_different_content_is_still_recorded(client: TestClient, tmp_path: Path) -> None:
    s = create(client)
    ready(client, s)
    assert post_frames(client, s, [0, 1, 2], seq=0).status_code == 204
    assert post_frames(client, s, [2], seq=0, shift=5.0).status_code == 204  # same batch, different t_ms
    assert post_frames(client, s, [1], seq=1).status_code == 204  # another batch claims an existing idx
    assert post_frames(client, s, [0], seq=0, jpeg=JPEG + b"x").status_code == 204  # different bytes
    assert [r["idx"] for r in rows(tmp_path, s)] == [0, 1, 2, 2, 1, 0]
    protocol = protocol_of(tmp_path, s)
    assert protocol.status == "protocol_error" and "integrity.duplicate_index" in protocol.reason_codes


def test_rows_beyond_the_cap_are_refused_even_for_reused_idx(client: TestClient) -> None:
    s = create(client)
    ready(client, s)
    for seq in range(29):
        assert post_frames(client, s, list(range(seq * 30, seq * 30 + 30)), seq=seq).status_code == 204
    # Altered re-sends add no JPEG but do add frames.jsonl rows; they count, so the file cannot grow unbounded.
    assert post_frames(client, s, list(range(30)), seq=29, shift=1.0).status_code == 204  # 900 rows
    assert post_frames(client, s, list(range(30)), seq=30, shift=2.0).status_code == 413


def test_exact_resend_after_complete_is_not_an_after_complete_attempt(client: TestClient, tmp_path: Path) -> None:
    s = create(client)
    ready(client, s)
    assert post_frames(client, s, [0, 1], seq=0).status_code == 204
    assert client.post(f"/api/sessions/{s['session_id']}/complete", headers=auth(s)).status_code == 202
    r = post_frames(client, s, [0, 1], seq=0)  # the lost-response retry lands after /complete
    assert r.status_code == 409 and r.json()["detail"] == "session_complete"
    session = json.loads((tmp_path / "data" / s["session_id"] / "session.json").read_text())
    assert session.get("after_complete_attempts", 0) == 0
    assert post_frames(client, s, [2], seq=1).status_code == 409  # new idx: a real late frame
    session = json.loads((tmp_path / "data" / s["session_id"] / "session.json").read_text())
    assert session["after_complete_attempts"] == 1
    assert [r["idx"] for r in rows(tmp_path, s)] == [0, 1]


def test_customer_payloads_have_no_scores(client: TestClient) -> None:
    s = create(client)
    sid = s["session_id"]
    responses = [client.post(f"/api/sessions/{sid}/preflight", headers=auth(s), json=preflight())]
    responses.append(client.get(f"/api/sessions/{sid}/challenge", headers=auth(s)))
    responses.append(post_frames(client, s, [0, 1, 2]))
    responses.append(client.post(f"/api/sessions/{sid}/complete", headers=auth(s)))
    for _ in range(50):
        status = client.get(f"/api/sessions/{sid}/status", headers=auth(s))
        responses.append(status)
        if status.json()["state"] == "done":
            break
        time.sleep(0.02)
    assert status.json() == {"state": "done", "message": "continue"}
    assert set(status.json()) == {"state", "message"}
    for r in responses:
        text = r.text.lower()
        assert not [w for w in FORBIDDEN if w in text], (r.request.url, r.text)


def test_status_waits_until_done(client: TestClient) -> None:
    s = create(client)
    assert client.get(f"/api/sessions/{s['session_id']}/status", headers=auth(s)).json() == {
        "state": "created", "message": "please_wait"}


def test_expired_session(client: TestClient, clock: Clock, tmp_path: Path) -> None:
    s = create(client)
    clock.ms += 15 * 60_000 + 1
    r = client.post(f"/api/sessions/{s['session_id']}/preflight", headers=auth(s), json=preflight())
    assert r.status_code == 410
    assert client.get(f"/api/sessions/{s['session_id']}/status", headers=auth(s)).status_code == 410
    assert json.loads((tmp_path / "data" / s["session_id"] / "session.json").read_text())["state"] == "expired"


def test_store_lists_newest_first(client: TestClient, clock: Clock) -> None:
    a = create(client)
    clock.ms += 1000
    b = create(client)
    ready(client, b)
    summaries = client.app.state.store.list()
    assert [x.session_id for x in summaries] == [b["session_id"], a["session_id"]]
    assert summaries[0].mode == "CAPABLE" and summaries[0].state == "capturing" and summaries[1].mode is None


def test_analysing_past_ttl_is_not_expired_anywhere(tmp_path: Path, clock: Clock) -> None:
    """A session past /complete never expires: the customer status and the store list agree (one state rule)."""
    settings = Settings(agent_passcode="pc", data_dir=tmp_path / "data2", fake_analysis=True)
    with TestClient(create_app(settings, runner=lambda *_: None, clock=clock)) as c:  # analysis never finishes
        s = create(c)
        ready(c, s)
        assert c.post(f"/api/sessions/{s['session_id']}/complete", headers=auth(s)).status_code == 202
        clock.ms += 16 * 60_000
        assert c.get(f"/api/sessions/{s['session_id']}/status", headers=auth(s)).json()["state"] == "analysing"
        assert c.app.state.store.list()[0].state == "analysing"
        stale = create(c)  # an unfinished session past its TTL reads expired in the list before anyone saves it so
        clock.ms += 16 * 60_000
        assert {x.session_id: x.state for x in c.app.state.store.list()}[stale["session_id"]] == "expired"
