"""turn.follow (family D, D.turn): the head turns the way the prompt asked, then comes back. New in this repo.

Window: the turn step's painted time to ended + 500 ms. yaw0 = the median yaw over the 500 ms before the prompt.
Signed excursion e(t) = (yaw - yaw0) x (+1 for "left", -1 for "right"); positive yaw is the person's own left
(CONTRACT section 1), so e > 0 means "towards the requested side".

Outcomes, first match wins:
1. the face is missing for more than 40% of the window: usable, risk 0.6, `turn.face_lost` (a hypothesis: swaps can
   drop the face at large angles; one family flagging leads to a retry, not to a human review);
2. turned the wrong way (wrong peak >= 15 degrees, requested peak < 10): usable, risk 1, `turn.wrong_direction`;
3. turned the right way (peak >= 15): usable, risk 0; `turn.no_return` when it did not come back within 10 degrees
   by the end (noted, not scored: a person may be slow to turn back);
4. otherwise the turn was not performed (or only partly): abstain `turn.not_performed`, because a genuine person may
   simply not have turned, and fusion's coverage rule handles a missing family.
A start under 150 ms after the prompt adds `turn.too_fast`, measured, not scored, until data says otherwise.
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, Plot, TurnStep

SPEC = specs.TURN_FOLLOW
MAX_PLOT_POINTS = 300


def _plot(t: np.ndarray, yaw: np.ndarray, painted: float, ended: float) -> Plot:
    ok = np.isfinite(yaw)
    tt, yy = t[ok], yaw[ok]
    step = max(1, int(np.ceil(len(tt) / MAX_PLOT_POINTS)))
    points = [(float(a), float(b)) for a, b in zip(tt[::step], yy[::step], strict=True)]
    return Plot(kind="turn", series={"yaw": points}, markers=[(painted, "painted"), (ended, "ended")])


def _crossing(t: np.ndarray, e: np.ndarray, seen: np.ndarray, level: float, painted: float) -> float | None:
    """Time after `painted` where e first rises through `level`, interpolated from the previous face frame (frames
    are 30-100 ms apart, longer than the effect being timed)."""
    idx = np.flatnonzero(seen)
    above = idx[e[idx] > level]
    if not len(above):
        return None
    j = int(above[0])
    prev = idx[idx < j]
    if len(prev) and e[prev[-1]] < level:
        k = int(prev[-1])
        return float(t[k] + (level - e[k]) / (e[j] - e[k]) * (t[j] - t[k]) - painted)
    return float(t[j] - painted)


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    plan, ch = ctx.bundle.plan, ctx.bundle.challenge
    if (plan is not None and not plan.run_turn) or ch is None:
        return []
    step = next((s for s in ch.steps if isinstance(s, TurnStep)), None)
    if step is None:
        return []
    ids = (SPEC.check_id, SPEC.family, SPEC.vote_group)
    event = next((e for e in ctx.bundle.events if e.step_id == step.step_id), None)
    if event is None or event.status != "shown" or event.painted_t_ms is None:
        why = f" ({event.skip_reason})" if event is not None and event.skip_reason else ""
        return [abstain(*ids, ["turn.not_performed"], f"The turn prompt was not shown{why}.", window_id=step.step_id)]

    p = ctx.thresholds.params(SPEC.check_id)
    painted = event.painted_t_ms
    ended = event.ended_t_ms if event.ended_t_ms is not None else painted + step.duration_ms
    end = ended + float(p.get("tail_ms", 500))
    window = ctx.quality.windows.get(step.step_id) if ctx.quality is not None else None
    if window is not None and "quality.low_fps" in window.reasons:
        return [abstain(*ids, ["quality.low_fps"], f"The camera delivered {window.fps:.1f} fps during the turn, too "
                        "few to follow the head.", features={"fps": window.fps}, window_id=step.step_id)]

    t, yaw = ctx.t, ctx.yaw
    before = (t >= painted - float(p.get("baseline_ms", 500))) & (t < painted) & np.isfinite(yaw)
    if before.sum() < 2:
        return [abstain(*ids, ["quality.no_face"], "The face was not found just before the turn prompt, so there is "
                        "no starting angle to compare with.", window_id=step.step_id)]
    yaw0 = float(np.median(yaw[before]))
    in_win = (t >= painted) & (t <= end)
    if not in_win.any():
        return [abstain(*ids, ["quality.low_fps"], "No frames arrived during the turn.", window_id=step.step_id)]
    seen = in_win & np.isfinite(yaw)
    face_present = float(seen.sum() / in_win.sum())
    sign = 1.0 if step.direction == "left" else -1.0
    e = (yaw - yaw0) * sign
    peak = float(np.max(e[seen])) if seen.any() else 0.0
    wrong = float(np.max(-e[seen])) if seen.any() else 0.0
    still = float(p.get("still_deg", 10))
    latency = _crossing(t, e, seen, still, painted)
    tail = seen & (t >= end - float(p.get("return_window_ms", 300)))
    ret = float(np.median(np.abs(yaw[tail] - yaw0))) if tail.any() else None
    features = {"peak_deg": peak, "wrong_peak_deg": wrong, "latency_ms": latency, "return_deg": ret,
                "face_present": face_present, "yaw0_deg": yaw0}
    plot = _plot(t[in_win | before], yaw[in_win | before], painted, ended)
    flag_at = ctx.thresholds.flag_at(SPEC.check_id, 0.5)
    source, voting = ctx.thresholds.source(SPEC.check_id), ctx.thresholds.voting(SPEC.check_id)
    asked = f"to their {step.direction}"

    def usable(risk: float, reasons: list[str], explanation: str) -> list[CheckResult]:
        if latency is not None and latency < float(p.get("too_fast_ms", 150)):
            reasons = [*reasons, "turn.too_fast"]
        return [result(*ids, risk=risk, flag_at=flag_at, quality=face_present, features=features, reasons=reasons,
                       explanation=explanation, source=source, window_id=step.step_id, plot=plot, voting=voting)]

    max_lost = float(p.get("max_face_lost", 0.4))
    if 1 - face_present > max_lost:
        return usable(float(p.get("face_lost_risk", 0.6)), ["turn.face_lost"],
                      f"The face was lost for {1 - face_present:.0%} of the turn (more than {max_lost:.0%}); a "
                      "hypothesis: a swapped face can drop out at large angles.")
    min_peak = float(p.get("min_peak_deg", 15))
    if wrong >= min_peak and peak < still:
        return usable(1.0, ["turn.wrong_direction"],
                      f"Asked to turn {asked}, the head turned {wrong:.0f} degrees the other way and at most "
                      f"{peak:.0f} degrees the way asked.")
    if peak >= min_peak:
        max_ret = float(p.get("max_return_deg", 10))
        lat = f" {latency:.0f} ms after the prompt" if latency is not None else ""
        if ret is not None and ret > max_ret:
            return usable(0.0, ["turn.no_return"],
                          f"The head turned {peak:.0f} degrees {asked}{lat} as asked, but was still {ret:.0f} "
                          "degrees away at the end (noted, not scored).")
        back = f" and came back within {ret:.0f} degrees" if ret is not None else ""
        return usable(0.0, [], f"The head turned {peak:.0f} degrees {asked}{lat} as asked{back}.")
    if face_present < float(ctx.thresholds.params("quality").get("min_face_present", 0.8)):
        return [abstain(*ids, ["quality.no_face"], f"The face was visible in {face_present:.0%} of the turn and "
                        f"moved at most {max(peak, wrong):.0f} degrees.", quality=face_present, features=features,
                        window_id=step.step_id)]
    return [abstain(*ids, ["turn.not_performed"], f"The head moved at most {max(peak, wrong):.0f} degrees after the "
                    f"prompt to turn {asked} (needs {min_peak:.0f} degrees), so the turn was not performed.",
                    quality=face_present, features=features, window_id=step.step_id)]
