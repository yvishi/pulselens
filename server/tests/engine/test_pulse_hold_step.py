"""P01: the dormant pulse-hold contract, before planner/browser integration."""

import pytest
from pydantic import ValidationError

from pulselens.contracts import Challenge, PulseHoldStep


@pytest.mark.parametrize(
    ("changes", "valid"),
    [({}, True), ({"start_offset_ms": 0}, True), ({"duration_ms": 0}, False),
     ({"duration_ms": -1}, False), ({"start_offset_ms": -1}, False),
     ({"kind": "colour"}, False), ({"unexpected": True}, False)],
)
def test_pulse_hold_step(changes: dict, valid: bool) -> None:
    payload = {"step_id": "p0", "start_offset_ms": 1500, "duration_ms": 12000, **changes}
    if valid:
        step = PulseHoldStep.model_validate(payload)
        assert step.kind == "pulse_hold"
        assert PulseHoldStep.model_validate_json(step.model_dump_json()) == step
        # A standalone type must not activate a step old clients cannot render.
        with pytest.raises(ValidationError):
            Challenge(session_id="synthetic", nonce="synthetic", mode="CAPABLE", baseline_ms=1500,
                      steps=[step.model_dump()], total_ms=15000)
    else:
        with pytest.raises(ValidationError):
            PulseHoldStep.model_validate(payload)
