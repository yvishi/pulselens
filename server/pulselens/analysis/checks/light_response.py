"""light.response (family C, C.response): the face answers today's colour sequence. Ported from the old
optical.light.delay check.

Per shown colour step, on the skin region:
- answered = an echo onset (echo.echo_onset) within the delay band, provisional [0, 300] ms;
- order_ok = the measured colour change points the way of the colour shown (cosine >= 0.5), which catches a
  recording of a different session's colours. A step that changed colour the wrong way counts as wrong order, not
  as no echo.
A step without an echo counts as silent only when its noise threshold could have heard one: at most half the median
echo of the answered steps of the same session, and never above `max_silent_threshold`. Otherwise it is unclear and
left out (the old repo's "unclear vs silent" fix; a bright-room webcam echo sits near the noise floor, SNR ~5), so
noisy capture leads to an abstain and a retry, never a flag.
Risk = 1 - (answered and order_ok) / valid steps. Needs at least 4 valid steps. One webcam frame (64-96 ms) is longer
than any lag limit, so the delay is a band, not a fine timing.

A step whose quality window (analysis/quality.py) is not usable (too dark or bright, clipped, the face moving or
missing, low fps) is left out, and its reasons join the abstain when too few steps remain.

Not run (no result) when the plan has no light or no colour step was shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.echo import EchoOnset, Response, echo_onset, response
from pulselens.analysis.reason_text import text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.linearize import srgb_to_linear
from pulselens.contracts import ChallengeEvent, CheckResult, ColourStep, Plot

SPEC = specs.LIGHT_RESPONSE
MAX_PLOT_POINTS = 300


@dataclass
class StepEcho:
    step_id: str
    painted: float
    onset: EchoOnset
    response: Response | None
    answered: bool
    order_ok: bool
    clear: bool = True  # False: no echo, but the threshold was too high to call the step silent
    window_reasons: list[str] = field(default_factory=list)  # blocking quality reasons of the step's window

    @property
    def ok(self) -> bool:
        return self.answered and self.order_ok

    @property
    def wrong_order(self) -> bool:
        """The face changed colour during the step, but not towards the colour shown."""
        r = self.response
        return r is not None and r.responded and not self.order_ok

    @property
    def valid(self) -> bool:
        return self.onset.valid and self.clear and not self.window_reasons


def colour_events(ctx: AnalysisContext) -> list[tuple[ColourStep, ChallengeEvent]]:
    """Colour steps the client reports as shown, with a painted time and colour, in step order."""
    ch = ctx.bundle.challenge
    if ch is None:
        return []
    shown = {e.step_id: e for e in ctx.bundle.events
             if e.status == "shown" and e.painted_t_ms is not None and e.shown_rgb is not None}
    return [(s, shown[s.step_id]) for s in ch.steps if isinstance(s, ColourStep) and s.step_id in shown]


def step_echoes(ctx: AnalysisContext) -> list[StepEcho]:
    p = ctx.thresholds.params(SPEC.check_id)
    echo = ctx.thresholds.params("echo")
    a_min = float(echo.get("a_min", 0.003))
    lo, hi = (float(x) for x in echo.get("delay_band_ms", (0, 300)))
    min_cos = float(p.get("min_cosine", 0.5))
    skin = ctx.regions["skin"]
    out = []
    for step, e in colour_events(ctx):
        colour = srgb_to_linear(np.asarray(e.shown_rgb, dtype=np.float64))
        ended = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.dwell_ms
        onset = echo_onset(ctx.t, skin, e.painted_t_ms, ended, colour, step_id=step.step_id, region="skin",
                           a_min=a_min)
        resp = response(ctx.t, skin, e.painted_t_ms, ended, colour, a_min=a_min) if onset.valid else None
        answered = onset.onset_ms is not None and lo <= onset.onset_ms <= hi
        order_ok = resp is not None and resp.responded and resp.cosine is not None and resp.cosine >= min_cos
        window = ctx.quality.windows.get(step.step_id) if ctx.quality is not None else None
        out.append(StepEcho(step.step_id, e.painted_t_ms, onset, resp, answered, order_ok,
                            window_reasons=window.blocking() if window is not None else []))
    # Silent only with the power to hear an echo: the session's own answered echoes, else the provisional cap.
    amps = [s.onset.amplitude for s in out if s.answered and not s.window_reasons and s.onset.amplitude is not None]
    hear = float(p.get("max_silent_threshold", 0.012))
    if amps:
        hear = min(hear, 0.5 * float(np.median(amps)))
    for s in out:
        silent = s.onset.valid and s.onset.onset_ms is None and not s.wrong_order
        s.clear = not silent or (s.onset.threshold is not None and s.onset.threshold <= hear)
    return out


def _plot(steps: list[StepEcho], markers: list[tuple[float, str]]) -> Plot:
    points = sorted((s.painted + float(tr), float(v)) for s in steps if s.onset.valid
                    for tr, v in zip(s.onset.t_rel, s.onset.p, strict=True))
    step = max(1, int(np.ceil(len(points) / MAX_PLOT_POINTS)))
    return Plot(kind="echo", series={"face": points[::step]}, markers=markers)


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    plan = ctx.bundle.plan
    if plan is not None and not plan.run_light:
        return []
    events = colour_events(ctx)
    if not events:
        return []
    ids = (SPEC.check_id, SPEC.family, SPEC.vote_group)
    q = ctx.thresholds.params("quality")
    p = ctx.thresholds.params(SPEC.check_id)

    overall = ctx.quality.overall
    min_fps = float(q.get("min_fps", 12))
    if "quality.low_fps" in overall.reasons:
        return [abstain(*ids, overall.blocking(), f"The camera delivered {overall.fps:.1f} fps, below the "
                        f"{min_fps:.0f} fps needed to time the light response.", features={"fps": overall.fps},
                        window_id="all")]
    if "quality.no_face" in overall.reasons:
        min_face = float(q.get("min_face_present", 0.8))
        return [abstain(*ids, overall.blocking(), f"The face was visible in {overall.face_present:.0%} of frames "
                        f"(need {min_face:.0%}).", quality=overall.face_present,
                        features={"face_present": overall.face_present}, window_id="all")]

    steps = step_echoes(ctx)
    valid = [s for s in steps if s.valid]
    unclear = sum(s.onset.valid and not s.clear and not s.window_reasons for s in steps)
    poor = [s for s in steps if s.window_reasons]
    min_steps = int(p.get("min_steps", 4))
    quality = len(valid) / len(steps)
    if len(valid) < min_steps:
        window_reasons = sorted({r for s in poor for r in s.window_reasons})
        why = f"; {unclear} were too noisy to tell an echo from silence" if unclear else ""
        if poor:
            why += f"; {len(poor)} had poor capture ({', '.join(text(r).rstrip('.').lower() for r in window_reasons)})"
        return [abstain(*ids, ["light.too_few_steps"] + ["light.weak_face_echo"] * (unclear > 0) + window_reasons,
                        f"Only {len(valid)} of {len(steps)} colour steps could be judged on the face (need "
                        f"{min_steps}){why}.", quality=quality,
                        features={"steps_valid": len(valid), "steps_shown": len(steps), "steps_unclear": unclear,
                                  "steps_poor_quality": len(poor)},
                        window_id="all")]

    answered = [s for s in valid if s.answered]
    n_ok = sum(s.ok for s in valid)
    n_wrong = sum(s.wrong_order for s in valid)
    n_silent = sum(not s.ok and not s.wrong_order for s in valid)
    risk = 1.0 - n_ok / len(valid)
    flag_at = ctx.thresholds.flag_at(SPEC.check_id, 0.5)
    lo, hi = (float(x) for x in ctx.thresholds.params("echo").get("delay_band_ms", (0, 300)))
    delay = float(np.median([s.onset.onset_ms for s in answered])) if answered else None
    snrs = [s.onset.snr for s in answered if s.onset.snr is not None]
    reasons = []
    if risk >= flag_at:
        reasons += ["light.no_echo"] * (n_silent > 0) + ["light.wrong_order"] * (n_wrong > 0)

    if answered:
        explanation = (f"The face answered {len(answered)} of {len(valid)} colour steps, {delay:.0f} ms after each "
                       f"(expected {lo:.0f} to {hi:.0f} ms)")
        explanation += f"; {n_wrong} changed towards the wrong colour." if n_wrong else "."
    elif n_wrong:
        explanation = (f"The face changed colour on {n_wrong} of {len(valid)} colour steps, but never towards the "
                       "colour shown, as a recording of another session would.")
    else:
        explanation = (f"The face did not answer any of the {len(valid)} colour steps, as a recording that never "
                       "saw this screen would.")
    return [
        result(
            *ids,
            risk=risk,
            flag_at=flag_at,
            quality=quality,
            features={
                "steps_valid": len(valid),
                "steps_answered": len(answered),
                "steps_order_ok": sum(s.order_ok for s in valid),
                "median_delay_ms": delay,
                "median_snr": float(np.median(snrs)) if snrs else None,
                "steps_unclear": unclear,
                "steps_poor_quality": len(poor),
            },
            reasons=reasons,
            explanation=explanation,
            source=ctx.thresholds.source(SPEC.check_id),
            window_id="all",
            plot=_plot([s for s in steps if s.onset.valid], [(s.painted, s.step_id) for s in steps]),
            voting=ctx.thresholds.voting(SPEC.check_id),
        )
    ]
