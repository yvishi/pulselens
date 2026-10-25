from pathlib import Path

import pytest
from scripts.calibrate import calibrate

from pulselens.analysis.thresholds import Thresholds
from tests.analysis.test_calibrate import SPEC, _rows


@pytest.mark.parametrize("risk", [0.0, 1e-18])
def test_numerically_zero_quantile_retains_provisional_floor(risk: float) -> None:
    provisional = Thresholds.load(calibrated=Path("missing-calibration.yaml"))
    out, report = calibrate(_rows([risk] * 30), provisional)
    assert SPEC.check_id not in out
    assert (SPEC.check_id, 30, provisional.flag_at(SPEC.check_id), "provisional") in report
