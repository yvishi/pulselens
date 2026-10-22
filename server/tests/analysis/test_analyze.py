from pathlib import Path

import numpy as np
import pytest

import pulselens.analysis as analysis
from pulselens.analysis import analyze, specs
from pulselens.analysis.__main__ import main as cli
from pulselens.analysis.context import build_context
from pulselens.analysis.landmarks import read_cache
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.thresholds import Thresholds
from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult
from tests.fixtures.synth import make_session


@pytest.fixture(scope="module")
def genuine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_session(tmp_path_factory.mktemp("genuine"), kind="genuine")


def _valid(results: list[CheckResult]) -> None:
    for r in results:
        CheckResult.model_validate(r.model_dump())


def test_analyze_on_a_genuine_bundle_returns_valid_results(genuine: Path) -> None:
    results = analyze(genuine)
    assert isinstance(results, list)
    _valid(results)


def test_analyze_on_an_empty_directory_abstains_and_does_not_raise(tmp_path: Path) -> None:
    results = analyze(tmp_path)
    assert {r.check_id for r in results} == {s.check_id for s in specs.ALL}
    assert all(r.status == "abstain" and r.risk is None and not r.flag for r in results)
    assert all(r.reason_codes == ["quality.no_frames"] for r in results)
    _valid(results)


def test_analyze_on_a_missing_directory_does_not_raise(tmp_path: Path) -> None:
    assert all(r.status == "abstain" for r in analyze(tmp_path / "nope"))


def test_analyze_with_a_corrupt_jpeg_does_not_raise(tmp_path: Path) -> None:
    path = make_session(tmp_path, kind="genuine", turn=None, n_colour=2)
    (path / "frames" / "000003.jpg").write_bytes(b"not a jpeg")
    ctx = build_context(load_bundle(path), Thresholds.load())
    assert not ctx.readable[3] and ctx.readable[4]
    assert np.isnan(ctx.regions["skin"].rgb_linear[3]).all()
    _valid(analyze(path))


def test_analyze_when_every_jpeg_is_corrupt(tmp_path: Path) -> None:
    path = make_session(tmp_path, kind="genuine", turn=None, n_colour=1)
    for f in (path / "frames").iterdir():
        f.write_bytes(b"")
    results = analyze(path)
    assert results and all(r.status == "abstain" for r in results)
    assert all(r.explanation.startswith("None of the") for r in results)  # read as unreadable, not as a crash


def test_context_measures_the_regions_and_the_yaw(genuine: Path) -> None:
    b = load_bundle(genuine)
    ctx = build_context(b, Thresholds.load())
    assert ctx.n == len(b.frames) and ctx.readable.all()
    skin = ctx.regions["skin"].rgb_linear
    assert np.isfinite(skin).all()
    assert skin[:, 0].mean() > skin[:, 2].mean()  # skin is redder than it is blue
    assert (ctx.regions["neck"].coverage == 1.0).all()
    assert np.nanmax(ctx.yaw) > 20  # the synthetic person turned to their own left
    assert ctx.face_box[0].tolist() == pytest.approx([120, 40, 80, 110])


def test_the_landmark_cache_is_used_as_is(genuine: Path) -> None:
    cache = read_cache(genuine)
    assert cache is not None and len(cache) == len(load_bundle(genuine).frames)
    assert len(cache[0]["landmarks"]) == 478


def test_no_face_gives_nan_regions_but_a_background(tmp_path: Path) -> None:
    path = make_session(tmp_path, kind="genuine", turn=None, n_colour=1, face_in_frames=False)
    ctx = build_context(load_bundle(path), Thresholds.load())
    assert np.isnan(ctx.regions["skin"].rgb_linear).all() and np.isnan(ctx.yaw).all()
    assert np.isfinite(ctx.regions["background"].rgb_linear).all()


def test_a_check_that_raises_becomes_an_abstain(genuine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    @guarded(specs.SENSOR_CADENCE, specs.SENSOR_DUPLICATES)
    def broken(ctx):
        raise ValueError("boom")

    def unguarded(ctx):
        raise RuntimeError("no guard")

    monkeypatch.setattr(analysis, "CHECKS", [broken, unguarded])
    results = analyze(genuine)
    assert [r.check_id for r in results] == ["sensor.cadence", "sensor.duplicates"]
    assert all(r.status == "abstain" and r.reason_codes == ["quality.check_error"] for r in results)


def test_result_flags_only_at_the_threshold_and_clips_risk() -> None:
    def make(risk: float, **kw) -> CheckResult:
        return result("light.response", "C", "C.response", risk=risk, flag_at=0.5, quality=1.0, features={},
                      reasons=[], explanation="x", source="provisional", **kw)

    assert make(0.5).flag and not make(0.49).flag
    assert make(1.7).risk == 1.0 and make(-1).risk == 0.0
    assert not make(0.9, voting=False).flag
    a = abstain("light.response", "C", "C.response", ["quality.low_fps"], "x")
    assert a.status == "abstain" and a.risk is None and not a.flag


def test_features_keep_finite_numbers_only() -> None:
    r = result("sensor.cadence", "B", "B.stream", risk=0, flag_at=0.6, quality=1, reasons=[], explanation="x",
               source="provisional", features={"a": 1, "b": float("nan"), "c": None, "d": float("inf")})
    assert r.features == {"a": 1.0}


def test_calibrated_thresholds_win_over_provisional() -> None:
    t = Thresholds({"light.response": {"flag_at": 0.5, "min_steps": 4}}, {"light.response": {"flag_at": 0.7}})
    assert t.flag_at("light.response") == 0.7 and t.source("light.response") == "calibrated"
    assert t.params("light.response")["min_steps"] == 4
    assert Thresholds.load().source("light.response") == "provisional"
    assert not Thresholds.load().voting("sensor.prnu")


def test_cli_prints_a_table(genuine: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli([str(genuine), "--plots"]) == 0
    assert capsys.readouterr().out.strip()
    assert cli([str(genuine / "missing")]) == 2
