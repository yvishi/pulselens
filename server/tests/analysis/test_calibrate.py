"""scripts/calibrate.py (G9): flag_at from set A genuine risks, never from set B."""

from pathlib import Path

import pytest
import yaml
from scripts.calibrate import MIN_GENUINE, Row, calibrate, main, set_a

from pulselens.analysis import specs
from pulselens.analysis.result import abstain, result
from pulselens.analysis.thresholds import Thresholds

PROVISIONAL = Thresholds.load(calibrated=Path("missing.yaml"))
SPEC = specs.LIGHT_RESPONSE


def _rows(risks, *, set_="A", kind="genuine") -> list[Row]:
    return [Row(f"s{i}", set_, kind, [result(SPEC, PROVISIONAL, risk=r, quality=1.0, features={}, reasons=[],
                                             explanation="x")])
            for i, r in enumerate(risks)]


def test_flag_at_sits_just_above_the_genuine_97_5th_percentile() -> None:
    risks = [i / 100 for i in range(40)]
    out, _ = calibrate(_rows(risks), PROVISIONAL)
    flag_at = out[SPEC.check_id]["flag_at"]
    assert out[SPEC.check_id]["n_genuine"] == 40 and out[SPEC.check_id]["source"] == "calibrated"
    assert flag_at == pytest.approx(0.38025)  # numpy's linear 97.5th percentile of 0.00..0.39
    assert sum(r >= flag_at for r in risks) == 1  # at most 1 genuine in 40 flagged


def test_all_genuine_at_zero_risk_keeps_provisional() -> None:
    out, report = calibrate(_rows([0.0] * 30), PROVISIONAL)
    assert SPEC.check_id not in out
    assert (SPEC.check_id, 30, PROVISIONAL.flag_at(SPEC.check_id), "provisional") in report


def test_fewer_than_20_genuine_keep_the_provisional_value() -> None:
    out, report = calibrate(_rows([0.1] * (MIN_GENUINE - 1)), PROVISIONAL)
    assert SPEC.check_id not in out
    assert (SPEC.check_id, MIN_GENUINE - 1, PROVISIONAL.flag_at(SPEC.check_id), "provisional") in report


def test_set_b_and_attacks_and_abstains_are_ignored() -> None:
    genuine = _rows([0.1] * 30)
    noise = (_rows([0.9] * 30, set_="B") + _rows([0.9] * 30, set_="B", kind="replay")
             + _rows([0.9] * 30, kind="replay"))
    abstains = [Row("a", "A", "genuine", [abstain(SPEC, ["quality.no_face"], "x")])] * 30
    assert set_a(noise) == _rows([0.9] * 30, kind="replay")
    out, _ = calibrate(genuine + noise + abstains, PROVISIONAL)
    assert out[SPEC.check_id]["n_genuine"] == 30 and out[SPEC.check_id]["flag_at"] == pytest.approx(0.1)


def test_checks_that_never_flag_are_not_calibrated() -> None:
    _, report = calibrate([], PROVISIONAL)
    ids = {check_id for check_id, *_ in report}
    assert specs.SENSOR_PRNU.check_id not in ids and specs.PULSE_COHERENCE.check_id not in ids
    assert ids == {s.check_id for s in specs.ALL if not s.never_flags}


def test_the_written_file_is_read_back_as_calibrated(tmp_path: Path) -> None:
    out, _ = calibrate(_rows([i / 100 for i in range(40)]), PROVISIONAL)
    path = tmp_path / "thresholds.calibrated.yaml"
    path.write_text(yaml.safe_dump(out), encoding="utf-8")
    t = Thresholds.load(calibrated=path)
    assert t.source(SPEC.check_id) == "calibrated" and t.flag_at(SPEC.check_id) == out[SPEC.check_id]["flag_at"]
    assert t.source(specs.TURN_FOLLOW.check_id) == "provisional"


def test_main_on_an_empty_folder_writes_an_empty_calibration(tmp_path: Path, capsys) -> None:
    (tmp_path / "sessions").mkdir()
    out = tmp_path / "cal.yaml"
    assert main(["--sessions", str(tmp_path / "sessions"), "--out", str(out)]) == 0
    assert yaml.safe_load(out.read_text(encoding="utf-8")) == {}
    assert "0 set A sessions" in capsys.readouterr().out
