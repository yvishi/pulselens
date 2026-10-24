"""audit.py hash chain (docs/tasks/keshav.md K8)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.config import Settings
from pulselens.engine.audit import GENESIS, append, canonical_json, verify
from tests.engine.api import JPEG, PREFLIGHT, SyncExecutor


def _lines(session_dir: Path) -> list[dict]:
    text = (session_dir / "audit.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def test_first_line_links_to_genesis(tmp_path: Path) -> None:
    h = append(tmp_path, "session.created", {"a": 1})
    (line,) = _lines(tmp_path)
    assert h == line["hash"]
    assert line["seq"] == 0
    assert line["type"] == "session.created"
    assert line["prev_hash"] == GENESIS
    assert line["payload_sha256"] == hashlib.sha256(b'{"a":1}').hexdigest()


def test_hash_formula(tmp_path: Path) -> None:
    append(tmp_path, "session.created", {"a": 1})
    (line,) = _lines(tmp_path)
    body = {k: v for k, v in line.items() if k != "hash"}
    expected = hashlib.sha256((line["prev_hash"] + canonical_json(body)).encode()).hexdigest()
    assert line["hash"] == expected


def test_chain_links(tmp_path: Path) -> None:
    h0 = append(tmp_path, "session.created", {"a": 1})
    h1 = append(tmp_path, "frames.batch", b"\xff\xd8raw")
    h2 = append(tmp_path, "decision.made", {"b": 2})
    lines = _lines(tmp_path)
    assert [ln["seq"] for ln in lines] == [0, 1, 2]
    assert [ln["hash"] for ln in lines] == [h0, h1, h2]
    assert lines[1]["prev_hash"] == h0
    assert lines[2]["prev_hash"] == h1
    assert lines[1]["payload_sha256"] == hashlib.sha256(b"\xff\xd8raw").hexdigest()


def _write_lines(session_dir: Path, lines: list[dict]) -> None:
    text = "".join(canonical_json(ln) + "\n" for ln in lines)
    (session_dir / "audit.jsonl").write_text(text, encoding="utf-8")


def test_chain_verifies(tmp_path: Path) -> None:
    append(tmp_path, "session.created", {"a": 1})
    append(tmp_path, "frames.batch", b"\xff\xd8raw")
    append(tmp_path, "decision.made", {"b": 2})
    assert verify(tmp_path) == (True, None)


def test_missing_file_is_valid(tmp_path: Path) -> None:
    assert verify(tmp_path) == (True, None)


def test_one_byte_change_detected(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"\xff\xd8abc\xff\xd9")
    append(tmp_path, "session.created", {"a": 1})
    append(tmp_path, "frames.batch", frame.read_bytes())
    append(tmp_path, "decision.made", {"b": 2})
    assert verify(tmp_path) == (True, None)

    flipped = bytearray(frame.read_bytes())
    flipped[3] ^= 0x01
    frame.write_bytes(bytes(flipped))
    lines = _lines(tmp_path)
    lines[1]["payload_sha256"] = hashlib.sha256(frame.read_bytes()).hexdigest()
    _write_lines(tmp_path, lines)
    assert verify(tmp_path) == (False, 2)


def test_one_byte_change_detected_first_line(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"\xff\xd8abc\xff\xd9")
    append(tmp_path, "frames.batch", frame.read_bytes())
    append(tmp_path, "decision.made", {"b": 2})

    flipped = bytearray(frame.read_bytes())
    flipped[3] ^= 0x01
    frame.write_bytes(bytes(flipped))
    lines = _lines(tmp_path)
    lines[0]["payload_sha256"] = hashlib.sha256(frame.read_bytes()).hexdigest()
    _write_lines(tmp_path, lines)
    assert verify(tmp_path) == (False, 1)


def test_reordered_lines_detected(tmp_path: Path) -> None:
    append(tmp_path, "session.created", {"a": 1})
    append(tmp_path, "frames.batch", b"\xff\xd8raw")
    append(tmp_path, "decision.made", {"b": 2})
    lines = _lines(tmp_path)
    _write_lines(tmp_path, [lines[0], lines[2], lines[1]])
    assert verify(tmp_path) == (False, 2)


def test_garbage_line_detected(tmp_path: Path) -> None:
    append(tmp_path, "session.created", {"a": 1})
    append(tmp_path, "frames.batch", b"\xff\xd8raw")
    append(tmp_path, "decision.made", {"b": 2})
    path = tmp_path / "audit.jsonl"
    raw = path.read_text(encoding="utf-8").splitlines()
    raw[1] = "{not json"
    path.write_text("\n".join(raw) + "\n", encoding="utf-8")
    assert verify(tmp_path) == (False, 2)


def test_api_flow_writes_events_in_order(tmp_path: Path) -> None:
    settings = Settings(agent_passcode="agent-pc", data_dir=tmp_path / "data", fake_analysis=True)
    agent = {"X-Agent-Passcode": "agent-pc"}

    def post_batch(client: TestClient, sid: str, h: dict, seq: int) -> None:
        idxs = range(seq * 20, seq * 20 + 20)
        meta = {"batch_seq": seq, "frames": [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480} for i in idxs]}
        r = client.post(f"/api/sessions/{sid}/frames", headers=h, data={"meta": json.dumps(meta)},
                        files={f"f{i}": (f"{i}.jpg", JPEG, "image/jpeg") for i in idxs})
        assert r.status_code == 204, r.text

    with TestClient(create_app(settings, executor=SyncExecutor())) as client:
        s = client.post("/api/sessions", json={}).json()
        sid = s["session_id"]
        h = {"Authorization": f"Bearer {s['customer_token']}"}
        assert client.post(f"/api/sessions/{sid}/preflight", headers=h, json=PREFLIGHT).status_code == 200
        assert client.get(f"/api/sessions/{sid}/challenge", headers=h).status_code == 200
        post_batch(client, sid, h, 0)
        post_batch(client, sid, h, 1)
        post_batch(client, sid, h, 0)  # exact re-send: adds nothing to the audit log
        ev = [{"step_id": "c0", "status": "shown", "painted_t_ms": 1510.0, "ended_t_ms": 1910.0,
               "shown_rgb": [0.6, 0.5, 0.3]}]
        assert client.post(f"/api/sessions/{sid}/events", headers=h, json=ev).status_code == 204
        assert client.post(f"/api/sessions/{sid}/complete", headers=h).status_code == 202
        assert client.get(f"/api/sessions/{sid}/result", headers=agent).json()["decision"]
        assert client.post(f"/api/sessions/{sid}/agent", headers=agent, json={"action": "approve"}).status_code == 204

    folder = tmp_path / "data" / sid
    assert [ln["type"] for ln in _lines(folder)] == [
        "session.created", "challenge.issued", "frames.batch", "frames.batch", "events.received",
        "analysis.done", "decision.made", "agent.action"]
    assert verify(folder) == (True, None)


def test_verify_audit_cli(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    append(tmp_path, "session.created", {"a": 1})
    append(tmp_path, "frames.batch", b"\xff\xd8raw")
    append(tmp_path, "decision.made", {"b": 2})

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "scripts/verify_audit.py", str(tmp_path)],
                              capture_output=True, text=True, cwd=repo_root)

    good = run()
    assert good.returncode == 0, good.stderr
    assert "ok:" in good.stdout

    lines = _lines(tmp_path)
    _write_lines(tmp_path, [lines[0], lines[2], lines[1]])
    bad = run()
    assert bad.returncode == 1
    assert "first bad line 2" in bad.stdout
