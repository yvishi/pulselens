import shutil
from pathlib import Path

import numpy as np
import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks.sensor_stream import cadence_features, duplicate_runs, run
from pulselens.analysis.context import AnalysisContext, build_context
from pulselens.analysis.thresholds import Thresholds
from pulselens.bundle import frame_name, load_bundle
from tests.fixtures.synth import make_session


def _ctx(path: Path) -> AnalysisContext:
    return build_context(load_bundle(path), Thresholds.load())


def _by_id(results) -> dict:
    return {r.check_id: r for r in results}


@pytest.fixture(scope="module")
def genuine_ctx(tmp_path_factory: pytest.TempPathFactory) -> AnalysisContext:
    return _ctx(make_session(tmp_path_factory.mktemp("g"), kind="genuine", turn=None))


def test_genuine_jittered_30_fps_is_not_flagged(genuine_ctx: AnalysisContext) -> None:
    r = _by_id(run(genuine_ctx))
    assert set(r) == {"sensor.cadence", "sensor.duplicates"}
    for x in r.values():
        assert x.status == "usable" and not x.flag and x.vote_group == "B.stream" and x.family == "B"
    assert r["sensor.cadence"].features["fps"] == pytest.approx(30, abs=1)
    assert r["sensor.duplicates"].features["dup_share"] == 0
    assert r["sensor.cadence"].plot is not None and r["sensor.cadence"].plot.kind == "cadence"


def test_a_1_2_s_gap_flags_a_stall(genuine_ctx: AnalysisContext) -> None:
    ctx = _ctx(genuine_ctx.bundle.path)
    ctx.t[100:] += 1200
    r = _by_id(run(ctx))["sensor.cadence"]
    assert r.flag and r.risk == 1.0 and "sensor.stall" in r.reason_codes
    assert r.features["longest_gap_ms"] > 1200
    assert f"{r.features['longest_gap_ms']:.0f} ms" in r.explanation


def test_a_virtual_camera_clock_is_too_regular(tmp_path: Path) -> None:
    r = _by_id(run(_ctx(make_session(tmp_path, kind="virtual_camera", turn=None))))["sensor.cadence"]
    assert r.risk >= 0.7 and r.flag and "sensor.too_regular" in r.reason_codes


def test_ten_percent_exact_repeats_flag_duplicates(tmp_path: Path) -> None:
    path = make_session(tmp_path, kind="genuine", turn=None)
    frames = path / "frames"
    n = len(list(frames.iterdir()))
    for i in range(10, n, 10):  # every 10th frame is a copy of the one before
        shutil.copyfile(frames / frame_name(i - 1), frames / frame_name(i))
    r = _by_id(run(_ctx(path)))["sensor.duplicates"]
    assert r.flag and r.risk == 1.0 and "sensor.duplicates" in r.reason_codes
    assert r.features["dup_share"] == pytest.approx(0.1, abs=0.01)
    assert r.features["longest_dup_run"] == 1


def test_twenty_frames_abstain(tmp_path: Path) -> None:
    ctx = _ctx(make_session(tmp_path, kind="genuine", turn=None, n_colour=0, fps=10))
    assert ctx.n == 20
    for r in run(ctx):
        assert r.status == "abstain" and r.risk is None and not r.flag


def test_a_corrupt_frame_is_not_a_duplicate(tmp_path: Path) -> None:
    path = make_session(tmp_path, kind="genuine", turn=None)
    (path / "frames" / frame_name(5)).write_bytes(b"")
    (path / "frames" / frame_name(6)).write_bytes(b"")
    r = _by_id(run(_ctx(path)))["sensor.duplicates"]
    assert r.status == "usable" and r.features["dup_share"] == 0


def test_cadence_features_on_known_intervals() -> None:
    t = np.arange(40) * 40.0
    f = cadence_features(t)
    assert f["fps"] == pytest.approx(25) and f["cv"] == pytest.approx(0) and f["exact_share"] == 1
    t[20:] += 500
    assert cadence_features(t)["longest_gap_ms"] == pytest.approx(540)


def test_duplicate_runs() -> None:
    dup = np.array([0, 1, 1, 0, 1, 0, 1, 1, 1], dtype=bool)
    assert duplicate_runs(dup) == 3
    assert duplicate_runs(np.zeros(4, dtype=bool)) == 0


def test_analyze_now_runs_the_stream_checks(tmp_path: Path) -> None:
    ids = {r.check_id for r in analyze(make_session(tmp_path, kind="genuine", turn=None, n_colour=2))}
    assert {"sensor.cadence", "sensor.duplicates"} <= ids
