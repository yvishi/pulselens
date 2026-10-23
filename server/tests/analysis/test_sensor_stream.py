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


@pytest.fixture
def genuine_ctx(synth) -> AnalysisContext:
    return synth.context(kind="genuine", turn=None)


def test_genuine_jittered_30_fps_is_not_flagged(genuine_ctx: AnalysisContext) -> None:
    r = _by_id(run(genuine_ctx))
    assert set(r) == {"sensor.cadence", "sensor.duplicates"}
    for x in r.values():
        assert x.status == "usable" and not x.flag and x.vote_group == "B.stream" and x.family == "B"
    assert r["sensor.cadence"].features["fps"] == pytest.approx(30, abs=1)
    assert r["sensor.duplicates"].features["dup_share"] == 0
    assert r["sensor.cadence"].plot is not None and r["sensor.cadence"].plot.kind == "cadence"


def test_a_1_2_s_gap_flags_a_stall(genuine_ctx: AnalysisContext) -> None:
    ctx = genuine_ctx
    ctx.t[100:] += 1200
    r = _by_id(run(ctx))["sensor.cadence"]
    assert r.flag and r.risk == 1.0 and "sensor.stall" in r.reason_codes
    assert r.features["longest_gap_ms"] > 1200
    assert f"{r.features['longest_gap_ms']:.0f} ms" in r.explanation


def test_a_virtual_camera_clock_is_too_regular(synth) -> None:
    r = _by_id(run(synth.context(kind="virtual_camera", turn=None)))["sensor.cadence"]
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


def test_twenty_frames_abstain(synth) -> None:
    ctx = synth.context(kind="genuine", turn=None, n_colour=0, fps=10)
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


def test_analyze_now_runs_the_stream_checks(synth) -> None:
    ids = {r.check_id for r in analyze(synth.session(kind="genuine", turn=None, n_colour=2))}
    assert {"sensor.cadence", "sensor.duplicates"} <= ids


def _drop(ctx: AnalysisContext, lo: int, hi: int, *, shift_ms: float = 0.0) -> AnalysisContext:
    """Removes frames lo..hi-1 (by position) from the frame list and times, as if they never arrived."""
    keep = np.r_[0:lo, hi:ctx.n]
    ctx.bundle.frames = [ctx.bundle.frames[i] for i in keep]
    ctx.t = ctx.t[keep]
    ctx.t[lo:] += shift_ms
    return ctx


def test_frames_lost_in_upload_are_not_a_stall(genuine_ctx: AnalysisContext) -> None:
    # Issue #33: idx 88 -> 200, a 3.7 s gap; the browser grabbed those frames but they never arrived.
    ctx = _drop(genuine_ctx, 89, 200)
    r = _by_id(run(ctx))["sensor.cadence"]
    assert r.status == "usable" and not r.flag and r.risk == 0, r.explanation
    assert "sensor.stall" not in r.reason_codes and "quality.frames_missing" in r.reason_codes
    assert r.features["frames_missing"] == 111 and r.features["longest_excluded_gap_ms"] > 3000
    assert r.features["longest_gap_ms"] < 100 and "lost in upload" in r.explanation


def test_a_real_stall_with_consecutive_frame_numbers_still_flags(genuine_ctx: AnalysisContext) -> None:
    ctx = genuine_ctx
    ctx.t[100:] += 1200  # frame numbers stay consecutive: the source delivered nothing for 1.2 s
    r = _by_id(run(_drop(ctx, 20, 60)))["sensor.cadence"]
    assert r.flag and "sensor.stall" in r.reason_codes and r.features["frames_missing"] == 40


def test_a_gap_while_the_page_was_hidden_is_not_a_stall(genuine_ctx: AnalysisContext) -> None:
    ctx = genuine_ctx
    ch = ctx.bundle.challenge
    step = ch.steps[2]
    due = ch.baseline_ms + step.start_offset_ms
    ev = next(e for e in ctx.bundle.events if e.step_id == step.step_id)
    ev.status, ev.painted_t_ms, ev.ended_t_ms, ev.shown_rgb, ev.skip_reason = "skipped", None, None, None, "page_hidden"
    ctx.t[ctx.t > due - 100] += 2000  # no frames for 2 s around the step, numbers consecutive
    r = _by_id(run(ctx))["sensor.cadence"]
    assert r.status == "usable" and not r.flag, r.explanation
    assert "quality.page_hidden" in r.reason_codes and "sensor.stall" not in r.reason_codes


def test_a_stall_away_from_the_hidden_page_still_flags(genuine_ctx: AnalysisContext) -> None:
    ctx = genuine_ctx
    ch = ctx.bundle.challenge
    ev = next(e for e in ctx.bundle.events if e.step_id == ch.steps[5].step_id)
    ev.status, ev.painted_t_ms, ev.ended_t_ms, ev.shown_rgb, ev.skip_reason = "skipped", None, None, None, "page_hidden"
    ctx.t[30:] += 1500  # early in the baseline, far from the skipped step
    r = _by_id(run(ctx))["sensor.cadence"]
    assert r.flag and "sensor.stall" in r.reason_codes


def test_cadence_features_leave_excluded_gaps_out() -> None:
    t = np.arange(40) * 40.0
    t[20:] += 3000
    excluded = np.zeros(39, dtype=bool)
    excluded[19] = True
    f = cadence_features(t, excluded)
    assert f["longest_gap_ms"] == pytest.approx(40) and f["longest_excluded_gap_ms"] == pytest.approx(3040)
    assert f["cv"] == pytest.approx(0) and f["excluded_gaps"] == 1
