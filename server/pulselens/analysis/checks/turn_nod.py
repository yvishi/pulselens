"""turn.nod (family D, D.nod): after the head turn, the person nods (down, then back up) when the prompt asks.

A second random live prompt: a replayed or pre-recorded video cannot know when it comes. Like turn.follow, it is
judged on the head angle, here the pitch from landmarks.jsonl. Window: the nod step's painted time to ended + 500 ms;
pitch0 = the median pitch over the 500 ms before the prompt. Excursion e(t) = |pitch - pitch0|: the check does not
rely on the pitch's sign (on 15 of 18 real S2 sessions a higher pitch brought the nose closer to the chin, so positive
looks like "down", but nothing here depends on it), so a nod that starts up instead of down still counts.

Outcomes, first match wins. It never flags (thresholds are provisional guesses until real nods are measured):
1. no step in the challenge: [] (not run; every session before challenge.extra_prompts);
2. the prompt was not shown: abstain `turn.nod_not_performed`;
3. window too dark, clipped, too few fps or no face: abstain with the quality reason (poor capture is not evidence);
4. nodded (peak >= 10 degrees): usable, risk 0; `turn.nod_no_return` when the head had not come back within 7 degrees
   by the end (noted, not scored); `turn.too_fast` when it started under 150 ms after the prompt (noted, not scored);
5. otherwise: abstain `turn.nod_not_performed`, and fusion asks for a fresh challenge (CONTRACT section 8, row 4).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.checks.turn_follow import _crossing
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, NodStep, Plot

SPEC = specs.TURN_NOD
MAX_PLOT_POINTS = 300
UNSEEN = ("quality.too_dark", "quality.clipped")


def _plot(t: np.ndarray, pitch: np.ndarray, painted: float, ended: float) -> Plot:
    ok = np.isfinite(pitch)
    tt, pp = t[ok], pitch[ok]
    step = max(1, int(np.ceil(len(tt) / MAX_PLOT_POINTS)))
    points = [(float(a), float(b)) for a, b in zip(tt[::step], pp[::step], strict=True)]
    return Plot(kind="turn", series={"pitch": points}, markers=[(painted, "painted"), (ended, "ended")])


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    ch = ctx.bundle.challenge
    step = next((s for s in ch.steps if isinstance(s, NodStep)), None) if ch is not None else None
    if step is None:
        return []
    p = ctx.thresholds.params(SPEC.check_id)
    event = next((e for e in ctx.bundle.events if e.step_id == step.step_id), None)
    if event is None or event.status != "shown" or event.painted_t_ms is None:
        why = f" ({event.skip_reason})" if event is not None and event.skip_reason else ""
        return [abstain(SPEC, ["turn.nod_not_performed"], f"The nod prompt was not shown{why}.",
                        window_id=step.step_id)]

    painted = event.painted_t_ms
    ended = event.ended_t_ms if event.ended_t_ms is not None else painted + step.duration_ms
    end = ended + float(p["tail_ms"])
    window = ctx.quality.windows.get(step.step_id)
    if window is not None and "quality.low_fps" in window.reasons:
        return [abstain(SPEC, ["quality.low_fps"], f"The camera delivered {window.fps:.1f} fps during the nod, too few "
                        "to follow the head.", features={"fps": window.fps}, window_id=step.step_id)]
    unseen = [r for r in UNSEEN if window is not None and r in window.reasons]
    if unseen:
        why = " and ".join(reason_text(r).rstrip(".").lower() for r in unseen)
        return [abstain(SPEC, unseen, f"Unable to judge the nod: {why}, so the head angle cannot be trusted.",
                        quality=window.luma_ok * (1 - window.saturated), window_id=step.step_id)]

    t, pitch = ctx.t, ctx.pitch
    before = (t >= painted - float(p["baseline_ms"])) & (t < painted) & np.isfinite(pitch)
    if before.sum() < 2:
        return [abstain(SPEC, ["quality.no_face"], "The face was not found just before the nod prompt, so there is no "
                        "starting angle to compare with.", window_id=step.step_id)]
    pitch0 = float(np.median(pitch[before]))
    in_win = (t >= painted) & (t <= end)
    if not in_win.any():
        return [abstain(SPEC, ["quality.low_fps"], "No frames arrived during the nod.", window_id=step.step_id)]
    seen = in_win & np.isfinite(pitch)
    face_present = float(seen.sum() / in_win.sum())
    if face_present < float(ctx.thresholds.param("quality", "min_face_present")):
        return [abstain(SPEC, ["quality.no_face"], f"The face was visible in {face_present:.0%} of the nod window.",
                        quality=face_present, features={"face_present": face_present}, window_id=step.step_id)]
    d = pitch - pitch0
    e = np.abs(d)
    peak = float(np.max(e[seen]))
    latency = _crossing(t, e, seen, float(p["still_deg"]), painted)
    tail = seen & (t >= end - float(p["return_window_ms"]))
    ret = float(np.median(e[tail])) if tail.any() else None
    features = {"peak_deg": peak, "peak_pos_deg": float(np.max(d[seen])), "peak_neg_deg": float(np.max(-d[seen])),
                "latency_ms": latency, "return_deg": ret, "face_present": face_present, "pitch0_deg": pitch0}
    plot = _plot(t[in_win | before], pitch[in_win | before], painted, ended)

    min_peak = float(p["min_peak_deg"])
    if peak < min_peak:
        return [abstain(SPEC, ["turn.nod_not_performed"], f"After the prompt to nod, the head tilted at most "
                        f"{peak:.0f} degrees up or down (needs {min_peak:.0f}), so the nod was not performed.",
                        quality=face_present, features=features, window_id=step.step_id)]
    reasons: list[str] = []
    lat = f" {latency:.0f} ms after the prompt" if latency is not None else ""
    explanation = f"The head nodded {peak:.0f} degrees{lat} as asked"
    if ret is not None and ret > float(p["max_return_deg"]):
        reasons.append("turn.nod_no_return")
        explanation += f", but was still {ret:.0f} degrees away at the end (noted, not scored)."
    else:
        explanation += f" and came back within {ret:.0f} degrees." if ret is not None else "."
    if latency is not None and latency < float(p["too_fast_ms"]):
        reasons.append("turn.too_fast")
    return [result(SPEC, ctx.thresholds, risk=0.0, quality=face_present, features=features, reasons=reasons,
                   explanation=explanation, window_id=step.step_id, plot=plot)]
