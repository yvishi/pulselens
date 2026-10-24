"""The analysis' checks, as listed in CONTRACT section 9 (Ganeev's rows)."""

from __future__ import annotations

from pulselens.analysis.result import CheckSpec

SENSOR_CADENCE = CheckSpec("sensor.cadence", "B", "B.stream")
SENSOR_DUPLICATES = CheckSpec("sensor.duplicates", "B", "B.stream")
SENSOR_MODE_PROBE = CheckSpec("sensor.mode_probe", "B", "B.probe")
SENSOR_REGIONS = CheckSpec("sensor.regions", "B", "B.regions")
SENSOR_PRNU = CheckSpec("sensor.prnu", "B", "B.prnu", never_flags=True)  # supporting only
LIGHT_RESPONSE = CheckSpec("light.response", "C", "C.response")
LIGHT_FACE_NECK = CheckSpec("light.face_neck", "C", "C.relative")
LIGHT_BACKGROUND = CheckSpec("light.background", "C", "C.relative")
TURN_FOLLOW = CheckSpec("turn.follow", "D", "D.turn")
TURN_IDENTITY = CheckSpec("turn.identity", "D", "D.identity")
VISUAL_SBI = CheckSpec("visual.sbi", "D", "D.detector")
PULSE_COHERENCE = CheckSpec("pulse.coherence", "A", "A.pulse", never_flags=True)  # logged only
TURN_NOD = CheckSpec("turn.nod", "D", "D.nod")
LIP_DIGITS = CheckSpec("visual.lip_digits", "D", "D.lips")

ALL: tuple[CheckSpec, ...] = (
    SENSOR_CADENCE, SENSOR_DUPLICATES, SENSOR_MODE_PROBE, SENSOR_REGIONS, SENSOR_PRNU,
    LIGHT_RESPONSE, LIGHT_FACE_NECK, LIGHT_BACKGROUND,
    TURN_FOLLOW, TURN_IDENTITY, VISUAL_SBI, PULSE_COHERENCE,
    TURN_NOD, LIP_DIGITS,
)
