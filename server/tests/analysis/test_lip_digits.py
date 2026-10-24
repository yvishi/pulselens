import numpy as np
import pytest

from pulselens.analysis.checks import visual_lip_digits
from pulselens.analysis.context import mouth_open
from tests.analysis.conftest import requalify
from tests.fixtures.synth import MOUTH_OPEN_PX, synthetic_landmarks

GENUINE = {"kind": "genuine", "n_colour": 0, "turn": "left", "nod": "performed"}


def _one(ctx):
    results = visual_lip_digits.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "visual.lip_digits" and r.family == "D" and r.vote_group == "D.lips"
    assert r.window_id == "digits"
    return r


def test_mouth_open_is_the_inner_lip_gap_over_the_face_height() -> None:
    lm = synthetic_landmarks()
    assert mouth_open(lm) == pytest.approx(4 / 110)
    assert np.isnan(mouth_open({k: v for k, v in lm.items() if k != 14}))


def test_the_nod_and_each_digit_get_a_quality_window_with_no_motion_rule(synth) -> None:
    ctx = synth.context(**GENUINE, digits="in_sync")
    assert {"t0", "n0", "d0", "d1", "d2"} <= set(ctx.quality.windows)
    assert all(ctx.quality.windows[w].usable for w in ("n0", "d0", "d1", "d2"))
    assert np.nanmax(ctx.pitch) > 15 and np.nanmax(ctx.mouth_open) > 0.09


def test_lips_moving_with_each_digit_are_in_sync(synth) -> None:
    ctx = synth.context(**GENUINE, digits="in_sync")
    r = _one(ctx)
    assert r.status == "usable" and not r.flag and r.risk == 0 and r.voting, r.explanation
    assert r.features["answered"] == 3 and r.features["digits_shown"] == 3
    assert r.features["speak_open"] == pytest.approx(MOUTH_OPEN_PX / 110, abs=0.005)
    assert r.features["quiet_open"] < 0.005
    assert 400 <= r.features["latency_ms"] < 600
    assert "no audio" in r.explanation and "not recognised" in r.explanation
    assert r.plot is not None and [label for _, label in r.plot.markers] == ["d0", "d1", "d2"]


def test_still_lips_abstain_not_performed_never_flag(synth) -> None:
    r = _one(synth.context(**GENUINE, digits="silent"))
    assert r.status == "abstain" and not r.flag and r.risk is None
    assert r.reason_codes == ["visual.digits_not_performed"]
    assert r.features["answered"] == 0


def test_a_talking_replay_is_out_of_sync_and_abstains(synth) -> None:
    r = _one(synth.context(**GENUINE, digits="out_of_sync"))
    assert r.status == "abstain" and not r.flag
    assert r.reason_codes == ["visual.digits_not_performed", "visual.lips_out_of_sync"]
    assert r.features["quiet_open"] >= 0.025


def test_lips_moving_late_between_the_digits_are_not_in_sync(synth) -> None:
    ctx = synth.context(**GENUINE, digits="in_sync")
    shown = [e for e in ctx.bundle.events if e.step_id.startswith("d")]
    lm_shift = np.zeros(ctx.n)  # move every opening 1.4 s later: into the quiet gaps
    for e in shown:
        on = (ctx.t >= e.painted_t_ms + 400) & (ctx.t <= e.painted_t_ms + 900)
        lm_shift[on] = -1
        late = (ctx.t >= e.painted_t_ms + 1800) & (ctx.t <= e.painted_t_ms + 2300)
        lm_shift[late] = 1
    rest = float(np.nanmedian(ctx.mouth_open))
    ctx.mouth_open = np.where(lm_shift == 1, rest + MOUTH_OPEN_PX / 110, np.where(lm_shift == -1, rest, ctx.mouth_open))
    r = _one(ctx)
    assert r.status == "abstain" and "visual.digits_not_performed" in r.reason_codes


def test_digits_not_shown_abstain(synth) -> None:
    r = _one(synth.context(**GENUINE, digits="not_shown"))
    assert r.status == "abstain" and r.reason_codes == ["visual.digits_not_performed"]


def test_no_digit_steps_are_not_run(synth) -> None:
    assert visual_lip_digits.run(synth.context(kind="genuine", n_colour=0, turn="left")) == []


@pytest.mark.parametrize(("nod", "digits", "outcome", "code"), [
    ("performed", "in_sync", "PASS", "fusion.pass"),
    ("skipped", "in_sync", "RETRY_STEP_UP", "fusion.challenge_not_done"),
    ("performed", "silent", "RETRY_STEP_UP", "fusion.challenge_not_done"),
])
def test_end_to_end_a_prompt_not_followed_is_a_fresh_challenge(synth, monkeypatch, nod, digits, outcome, code) -> None:
    from pulselens.analysis import analyze
    from pulselens.analysis.vision import sbi
    from pulselens.bundle import load_bundle
    from pulselens.engine.fusion import fuse
    from pulselens.engine.integrity import check_integrity
    from pulselens.engine.reason_text import reason_text

    monkeypatch.setattr(sbi, "get_model", lambda: None)
    path = synth.session(kind="genuine", nod=nod, digits=digits)
    bundle = load_bundle(path)
    results = check_integrity(bundle) + analyze(path)
    assert {r.check_id for r in results} >= {"turn.follow", "turn.nod", "visual.lip_digits"}
    assert not any(r.flag for r in results), [r.explanation for r in results if r.flag]
    d = fuse(results, bundle.plan, 1, decided_at_ms=0)
    assert d.outcome == outcome and d.reasons[0] == reason_text(code), d.reasons
    if outcome != "PASS":
        assert d.step_up == "fresh_challenge"


def test_no_face_while_the_digits_are_shown_abstains_on_quality(synth) -> None:
    ctx = synth.context(**GENUINE, digits="in_sync")
    first = next(e for e in ctx.bundle.events if e.step_id == "d0")
    gone = ctx.t >= first.painted_t_ms
    ctx.mouth_open[gone] = np.nan
    ctx.face_box[gone] = np.nan
    r = _one(requalify(ctx))
    assert r.status == "abstain" and "quality.no_face" in r.reason_codes and not r.flag
