"""K7: the agent API (docs/CONTRACT.md section 2, rows 9 to 12)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.config import Settings

PASS = {"X-Agent-Passcode": "agent-pc"}
JPEG = b"\xff\xd8\xff\xd9"
PRE = {"user_agent": "t", "platform": "desktop", "browser": "b", "camera_label": "c", "width": 640, "height": 480,
       "measured_fps": 30.0, "dropped_frame_ratio": 0.0, "blur": 1.0, "brightness": 120.0, "face_found": True,
       "face_fraction": 0.1, "controls": [], "gyro": False, "no_flash_requested": False, "clock": "now", "probe": []}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(agent_passcode="agent-pc", data_dir=tmp_path / "data", fake_analysis=True)
    with TestClient(create_app(settings)) as c:
        yield c


def run_session(client: TestClient, *, complete: bool = True) -> dict:
    s = client.post("/api/sessions", json={}).json()
    h = {"Authorization": f"Bearer {s['customer_token']}"}
    sid = s["session_id"]
    client.post(f"/api/sessions/{sid}/preflight", headers=h, json=PRE)
    client.get(f"/api/sessions/{sid}/challenge", headers=h)
    for seq in range(3):
        idxs = range(seq * 20, seq * 20 + 20)
        meta = {"batch_seq": seq, "frames": [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480} for i in idxs]}
        client.post(f"/api/sessions/{sid}/frames", headers=h, data={"meta": json.dumps(meta)},
                    files={f"f{i}": (f"{i}.jpg", JPEG, "image/jpeg") for i in idxs})
    if complete:
        client.post(f"/api/sessions/{sid}/complete", headers=h)
        for _ in range(100):
            if client.get(f"/api/sessions/{sid}/result", headers=PASS).json()["decision"]:
                break
            time.sleep(0.02)
    return s


def test_passcode_required_everywhere(client: TestClient) -> None:
    s = run_session(client, complete=False)
    sid = s["session_id"]
    customer = {"Authorization": f"Bearer {s['customer_token']}", "X-Agent-Passcode": "wrong"}
    for method, url in [("get", "/api/sessions"), ("get", f"/api/sessions/{sid}/result"),
                        ("get", f"/api/sessions/{sid}/frames/0.jpg"), ("post", f"/api/sessions/{sid}/agent")]:
        kwargs = {"json": {"action": "approve"}} if method == "post" else {}
        assert getattr(client, method)(url, **kwargs).status_code == 401, url
        assert getattr(client, method)(url, headers=customer, **kwargs).status_code == 401, url  # customer ≠ agent


def test_list_newest_first_with_mode_and_outcome(client: TestClient) -> None:
    first = run_session(client)
    second = run_session(client, complete=False)
    rows = client.get("/api/sessions", headers=PASS).json()
    assert [r["session_id"] for r in rows][:2] == [second["session_id"], first["session_id"]]
    by_id = {r["session_id"]: r for r in rows}
    assert by_id[first["session_id"]]["outcome"] == "PASS" and by_id[first["session_id"]]["mode"] == "CAPABLE"
    assert by_id[second["session_id"]]["outcome"] is None


def test_result_before_and_after_the_decision(client: TestClient) -> None:
    s = run_session(client, complete=False)
    before = client.get(f"/api/sessions/{s['session_id']}/result", headers=PASS).json()
    assert before["decision"] is None and before["frame_count"] == 60 and before["state"] == "capturing"
    assert before["plan"]["mode"] == "CAPABLE" and len(before["challenge"]["steps"]) == 7
    done = run_session(client)
    report = client.get(f"/api/sessions/{done['session_id']}/result", headers=PASS).json()
    assert report["state"] == "done" and report["decision"]["outcome"] == "PASS"
    assert [r["check_id"] for r in report["results"]][:2] == ["integrity.protocol", "integrity.coverage"]
    assert report["agent_decision"] is None


def test_frame_jpeg_and_404(client: TestClient) -> None:
    s = run_session(client, complete=False)
    r = client.get(f"/api/sessions/{s['session_id']}/frames/3.jpg", headers=PASS)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content == JPEG
    assert client.get(f"/api/sessions/{s['session_id']}/frames/999.jpg", headers=PASS).status_code == 404
    assert client.get("/api/sessions/0000000000000000/frames/0.jpg", headers=PASS).status_code == 404


def test_agent_action_needs_a_decision_and_is_recorded(client: TestClient, tmp_path: Path) -> None:
    pending = run_session(client, complete=False)
    r = client.post(f"/api/sessions/{pending['session_id']}/agent", headers=PASS, json={"action": "approve"})
    assert r.status_code == 409
    s = run_session(client)
    sid = s["session_id"]
    r = client.post(f"/api/sessions/{sid}/agent", headers=PASS, json={"action": "escalate", "note": "check ID"})
    assert r.status_code == 204
    stored = json.loads((tmp_path / "data" / sid / "agent.json").read_text())
    assert stored["action"] == "escalate" and stored["note"] == "check ID" and stored["at_ms"] > 0
    assert client.get(f"/api/sessions/{sid}/result", headers=PASS).json()["agent_decision"] == {
        "action": "escalate", "note": "check ID"}
    assert client.post(f"/api/sessions/{sid}/agent", headers=PASS, json={"action": "fire"}).status_code == 422


def test_unknown_session_is_404(client: TestClient) -> None:
    assert client.get("/api/sessions/0000000000000000/result", headers=PASS).status_code == 404
