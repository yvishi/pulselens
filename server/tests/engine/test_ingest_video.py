"""Test video ingestion script: scripts/ingest_video.py."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from ingest_video import ingest_video  # noqa: E402

from pulselens.bundle import load_bundle  # noqa: E402


def _make_dummy_video(path: Path, n_frames: int = 90, fps: float = 30.0, w: int = 320, h: int = 240) -> Path:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    for i in range(n_frames):
        # Draw gradient frame with a mock face ellipse
        frame = np.full((h, w, 3), (i % 256, 120, 80), dtype=np.uint8)
        cv2.ellipse(frame, (w // 2, h // 2), (w // 4, h // 3), 0, 0, 360, (200, 180, 150), -1)
        out.write(frame)
    out.release()
    return path


def test_ingest_video_roundtrip(tmp_path: Path) -> None:
    video_path = tmp_path / "judge_clip.mp4"
    _make_dummy_video(video_path, n_frames=60, fps=30.0)

    data_dir = tmp_path / "sessions"
    session_dir = ingest_video(
        video_path,
        data_dir=data_dir,
        label_kind="replay_screen",
        label_tool="phone_screen",
        fake_analysis=True,
    )

    assert session_dir.exists()
    assert (session_dir / "session.json").exists()
    assert (session_dir / "preflight.json").exists()
    assert (session_dir / "challenge.json").exists()
    assert (session_dir / "results.json").exists()
    assert (session_dir / "decision.json").exists()
    assert (session_dir / "audit.jsonl").exists()

    bundle = load_bundle(session_dir)
    assert bundle.session["state"] == "done"
    assert bundle.label is not None
    assert bundle.label.kind == "replay_screen"
    assert len(bundle.frames) >= 60
    assert len(bundle.events) > 0
    assert bundle.decision is not None

    # Check audit chain passes verification
    from pulselens.engine.audit import verify
    ok, bad_line = verify(session_dir)
    assert ok is True
    assert bad_line is None


def test_ingest_video_cli(tmp_path: Path) -> None:
    import subprocess
    video_path = tmp_path / "cli_clip.mp4"
    _make_dummy_video(video_path, n_frames=45, fps=30.0)

    data_dir = tmp_path / "cli_sessions"
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[3] / "scripts" / "ingest_video.py"),
        str(video_path),
        "--data-dir",
        str(data_dir),
        "--fake-analysis",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Session created:" in res.stdout
    assert "Console URL:" in res.stdout


def test_ingest_video_empty_fails(tmp_path: Path) -> None:
    empty_video = tmp_path / "empty.mp4"
    empty_video.write_bytes(b"")

    with pytest.raises(ValueError, match="Could not open|No frames"):
        ingest_video(empty_video, data_dir=tmp_path / "sessions")
