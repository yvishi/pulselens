"""visual.lip_digits (family D, D.lips): the lips move when each random digit appears, and are quiet in between.

The challenge shows 3 random digits one at a time at random gaps; the person reads each aloud. **What this checks,
honestly:** the timing of lip movement against the random digit times, nothing more. No audio is captured, and the
digit spoken is not recognised (that would need a lip-reading model), so a person saying the wrong number passes,
and a live face swap passes too (it copies the attacker's real lips). What it defeats is a replayed, pre-recorded or
animated face: it cannot know when this session's digits appear.

Per frame: mouth_open = the inner-lip gap (landmarks 13-14) over the face height (10-152), from the context.
m0 = its median over the 800 ms before the first digit; activity a(t) = |mouth_open - m0|.
- Each digit k (painted at p_k) answers when a reaches `min_open` (0.025) within [p_k + 150, p_k + 1200] ms.
- Quiet frames: the 800 ms before the first digit, and from p_k + 1500 ms to the next digit's window (and 1 s after
  the last digit). quiet = the 90th percentile of a there.
- In sync: at least `min_answered` (2 of 3) digits answered, and the median digit peak >= `min_contrast` (2) x quiet.

Outcomes, first match wins. It never flags: a prompt not followed is a fresh challenge, never attack evidence
(thresholds are provisional guesses until real sessions with digits are measured):
1. no digit step in the challenge: [] (not run; every session before challenge.extra_prompts);
2. no digit was shown: abstain `visual.digits_not_performed`;
3. a digit window too dark, clipped, too few fps or no face: abstain with the quality reason;
4. in sync: usable, risk 0;
5. otherwise abstain `visual.digits_not_performed` (plus `visual.lips_out_of_sync` when the lips did move, but not
   with the digits): fusion asks for a fresh challenge (CONTRACT section 8, row 4).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, DigitStep, Plot

SPEC = specs.LIP_DIGITS
MAX_PLOT_POINTS = 300
UNSEEN = ("quality.no_face", "quality.too_dark", "quality.clipped", "quality.low_fps")
AFTER_LAST_MS = 1000.0  # quiet frames after the last digit: from p_last + quiet_after_ms, this long


def _plot(t: np.ndarray, a: np.ndarray, markers: list[tuple[float, str]]) -> Plot:
    ok = np.isfinite(a)
    tt, aa = t[ok], a[ok]
    step = max(1, int(np.ceil(len(tt) / MAX_PLOT_POINTS)))
    points = [(float(x), float(y)) for x, y in zip(tt[::step], aa[::step], strict=True)]
    return Plot(kind="turn", series={"mouth_activity": points}, markers=markers)  # a motion trace, like the turn's


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    ch = ctx.bundle.challenge
    steps = [s for s in ch.steps if isinstance(s, DigitStep)] if ch is not None else []
    if not steps:
        return []
    p = ctx.thresholds.params(SPEC.check_id)
    events = {e.step_id: e for e in ctx.bundle.events if e.status == "shown" and e.painted_t_ms is not None}
    shown = [(s, events[s.step_id].painted_t_ms) for s in steps if s.step_id in events]
    if not shown:
        return [abstain(SPEC, ["visual.digits_not_performed"], "The digits to read aloud were not shown.",
                        window_id="digits")]

    bad = sorted({r for s, _ in shown for r in (ctx.quality.windows[s.step_id].reasons
                                                 if s.step_id in ctx.quality.windows else []) if r in UNSEEN})
    if bad:
        why = " and ".join(reason_text(r).rstrip(".").lower() for r in bad)
        return [abstain(SPEC, bad, f"Unable to judge the lips while the digits were shown: {why}.",
                        window_id="digits")]

    t, m = ctx.t, ctx.mouth_open
    seen = np.isfinite(m)
    lo, hi = float(p["min_latency_ms"]), float(p["max_latency_ms"])
    quiet_after, min_open = float(p["quiet_after_ms"]), float(p["min_open"])
    first = shown[0][1]
    rest = seen & (t >= first - float(p["baseline_ms"])) & (t < first)
    if rest.sum() < 2:
        return [abstain(SPEC, ["quality.no_face"], "The face was not found just before the first digit, so there is no "
                        "resting mouth to compare with.", window_id="digits")]
    m0 = float(np.median(m[rest]))
    a = np.abs(m - m0)

    peaks, latencies = [], []
    quiet = rest & (t < first + lo)
    for k, (_, painted) in enumerate(shown):
        win = seen & (t >= painted + lo) & (t <= painted + hi)
        peaks.append(float(np.max(a[win])) if win.any() else 0.0)
        crossed = t[seen & (t >= painted) & (t <= painted + hi) & (a >= min_open)]
        if len(crossed):
            latencies.append(float(crossed[0] - painted))
        nxt = shown[k + 1][1] + lo if k + 1 < len(shown) else painted + quiet_after + AFTER_LAST_MS
        quiet |= seen & (t >= painted + quiet_after) & (t < nxt)
    answered = sum(pk >= min_open for pk in peaks)
    speak = float(np.median(peaks))
    quiet_level = float(np.percentile(a[quiet], 90)) if quiet.any() else 0.0
    features = {"answered": answered, "digits_shown": len(shown), "speak_open": speak, "quiet_open": quiet_level,
                "rest_open": m0, "latency_ms": float(np.median(latencies)) if latencies else None}
    span = (t >= first - float(p["baseline_ms"])) & (t <= shown[-1][1] + quiet_after + AFTER_LAST_MS)
    plot = _plot(t[span], a[span], [(painted, s.step_id) for s, painted in shown])
    n = len(shown)

    min_answered = min(int(p["min_answered"]), n)
    in_sync = answered >= min_answered and speak >= float(p["min_contrast"]) * quiet_level
    if in_sync:
        lat = f", {features['latency_ms']:.0f} ms after each appeared (median)" if latencies else ""
        return [result(SPEC, ctx.thresholds, risk=0.0, quality=1.0, features=features, reasons=[],
                       explanation=f"The lips opened for {answered} of {n} digits{lat}, and were quieter between them "
                       f"(opening {speak:.3f} vs {quiet_level:.3f} of the face height). Timing only: no audio, and the "
                       "digit spoken is not recognised.", window_id="digits", plot=plot)]
    moved = max(speak, quiet_level) >= min_open
    reasons = ["visual.digits_not_performed"] + (["visual.lips_out_of_sync"] if moved else [])
    if moved:
        explanation = (f"The lips moved, but not with the digits: they opened for {answered} of {n} digits and as "
                       f"much between them (opening {speak:.3f} with a digit vs {quiet_level:.3f} between), so the "
                       "digits were not read aloud on cue.")
    else:
        explanation = (f"The lips stayed still while the digits were shown (largest opening {speak:.3f} of the face "
                       f"height, needs {min_open:.3f}), so the digits were not read aloud.")
    return [abstain(SPEC, reasons, explanation, quality=1.0, features=features, window_id="digits")]
