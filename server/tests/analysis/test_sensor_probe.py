import pytest

from pulselens.analysis.checks import sensor_probe
from pulselens.contracts import ModeProbe

HD, VGA, ODD = (1280, 720, 30), (640, 480, 30), (1000, 750, 24)


def _row(requested, accepted=True, delivered=None, switch_ms=None, frames_missing=None) -> ModeProbe:
    return ModeProbe(requested=requested, accepted=accepted, delivered=delivered, switch_ms=switch_ms,
                     frames_missing=frames_missing)


def _run(synth, rows):
    ctx = synth.context(kind="genuine", turn=None, n_colour=2)
    ctx.bundle.preflight = ctx.bundle.preflight.model_copy(update={"probe": rows})
    results = sensor_probe.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "sensor.mode_probe" and r.family == "B" and r.vote_group == "B.probe"
    return r


def test_the_chromium_fake_camera_pattern_is_too_perfect(synth) -> None:
    # The old repo's measurement: the fake camera accepted 1000x750 and switched in 57-105 ms with 0 frames lost.
    r = _run(synth, [_row(HD, delivered=(1280, 720), switch_ms=60, frames_missing=0),
                     _row(VGA, delivered=(640, 480), switch_ms=40, frames_missing=0),
                     _row(ODD, delivered=(1000, 750), switch_ms=57, frames_missing=0)])
    assert r.status == "usable" and r.risk == pytest.approx(0.7) and r.flag
    assert r.reason_codes == ["sensor.probe_too_perfect"] and r.features["accepted_unusual"] == 1
    assert "57 ms" in r.explanation and "hypothesis" in r.explanation


def test_a_real_webcam_refusing_the_unusual_mode_is_not_flagged(synth) -> None:
    r = _run(synth, [_row(HD, delivered=(1280, 720), switch_ms=420, frames_missing=6),
                     _row(VGA, delivered=(640, 480), switch_ms=380, frames_missing=5),
                     _row(ODD, accepted=False)])
    assert r.status == "usable" and r.risk == 0 and not r.flag
    assert r.features["accepted_unusual"] == 0 and r.features["median_switch_ms"] == 400
    assert r.features["frames_missing_total"] == 11


def test_a_slow_switch_to_the_unusual_mode_is_not_too_perfect(synth) -> None:
    r = _run(synth, [_row(VGA, delivered=(640, 480), switch_ms=300, frames_missing=4),
                     _row(ODD, delivered=(1000, 750), switch_ms=600, frames_missing=8)])
    assert r.risk == 0 and not r.flag


def test_settings_that_change_while_the_frames_do_not_are_a_phantom_switch(synth) -> None:
    # Synthetic sessions run at 320x240: the camera accepted 1280x720, but 320x240 frames kept coming.
    r = _run(synth, [_row(HD, delivered=(320, 240), switch_ms=None, frames_missing=None),
                     _row(ODD, accepted=False)])
    assert r.risk == 1.0 and r.flag and r.reason_codes == ["sensor.phantom_switch"]
    assert "1280x720" in r.explanation


@pytest.mark.parametrize("rows", [[], [_row(HD, accepted=False), _row(VGA, accepted=False), _row(ODD, accepted=False)]])
def test_no_probe_or_nothing_accepted_abstains_as_unsupported(synth, rows) -> None:
    r = _run(synth, rows)
    assert r.status == "abstain" and r.risk is None and not r.flag
    assert r.reason_codes == ["sensor.probe_not_run"] and "unsupported, not failed" in r.explanation
