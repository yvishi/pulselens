"""Thresholds have no code defaults (T13): every value lives in thresholds.yaml, and a missing one is loud."""

import pytest

from pulselens.analysis.checks import light_response
from pulselens.analysis.thresholds import PROVISIONAL, Thresholds, _read


def test_a_missing_value_is_a_key_error() -> None:
    t = Thresholds({"light.response": {"min_steps": 4}})
    assert t.param("light.response", "min_steps") == 4
    with pytest.raises(KeyError, match="light.response.flag_at"):
        t.flag_at("light.response")
    with pytest.raises(KeyError):
        t.param("quality", "min_fps")


def test_calibrated_values_win_and_voting_is_an_optional_switch() -> None:
    t = Thresholds({"turn.follow": {"flag_at": 0.5}}, {"turn.follow": {"flag_at": 0.7}})
    assert t.param("turn.follow", "flag_at") == 0.7 and t.source("turn.follow") == "calibrated"
    assert t.voting("turn.follow") and not Thresholds({"x.y": {"voting": False}}).voting("x.y")


def test_a_check_with_a_missing_value_abstains_with_check_error(synth) -> None:
    ctx = synth.context(kind="genuine", turn=None)
    full = _read(PROVISIONAL)
    ctx.thresholds = Thresholds({**full, "light.response": {k: v for k, v in full["light.response"].items()
                                                              if k != "min_steps"}})
    (r,) = light_response.run(ctx)
    assert r.status == "abstain" and r.reason_codes == ["quality.check_error"] and not r.flag
