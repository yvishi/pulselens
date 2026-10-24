"""light.response (family C, C.response): the face answers today's colour sequence. Ported from the old
optical.light.delay check.

Per shown colour step, on the skin region:
- answered = an echo onset (echo.echo_onset) within the delay band, provisional [0, 300] ms;
- order_ok = the measured colour change points the way of the colour shown (cosine >= 0.5), which catches a
  recording of a different session's colours. A step that changed colour the wrong way counts as wrong order, not
  as no echo.
A step that cannot be judged either way is unclear and left out, so weak or noisy capture leads to an abstain and a
retry, never a flag (AGENTS.md rule 3; issue #17, a genuine bright-room webcam session that was flagged):
- "noisy": no echo, and the noise threshold could not have heard one: above half the median echo of the session's
  answered steps, or above `max_silent_threshold` (the old repo's "unclear vs silent" fix);
- "faint": no echo, but the steps without one, pooled, still push towards the colours shown (`faint_echo_z` >=
  2.5 standard errors): the face answered below the onset threshold, as under weak light, which a recording that
  never saw this screen does not;
- "weak_colour": an echo, but its colour change is under `order_min_snr` x its threshold, too small to read its
  direction. Only a clear change the wrong way counts as wrong order.
A step whose baseline drifts (a camera still settling) is invalid in echo.echo_onset and left out too.
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
from pulselens.analysis.checks.light_common import colour_events, light_not_run, session_abstain
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.echo import EchoOnset, Response, echo_onset, response
from pulselens.analysis.reason_text import reason_text
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.linearize import srgb_to_linear
from pulselens.contracts import CheckResult, Plot

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
    strong: bool = False  # the colour change is at least `order_min_snr` x its threshold: its direction can be read
    clear: bool = True  # False: the step cannot be judged either way (see `unclear`)
    unclear: str | None = None  # "noisy", "faint" or "weak_colour"
    window_reasons: list[str] = field(default_factory=list)  # blocking quality reasons of the step's window

    @property
    def ok(self) -> bool:
        return self.answered and self.order_ok

    @property
    def wrong_order(self) -> bool:
        """The face changed colour clearly during the step, but not towards the colour shown."""
        return self.strong and not self.order_ok

    @property
    def silent(self) -> bool:
        """No echo onset and no clear wrong-colour change: silent, or unclear (decided in step_echoes)."""
        return self.onset.valid and self.onset.onset_ms is None and not self.wrong_order

    @property
    def valid(self) -> bool:
        return self.onset.valid and self.clear and not self.window_reasons


def faint_echo_z(steps: list[StepEcho]) -> float | None:
    """The steps without an echo, pooled (Stouffer): their mean push towards the colour shown, in standard errors.
    Near 0 when the light never reached the face; well above it when the face answered below the onset threshold."""
    z = [s.onset.hold_z for s in steps if s.silent and not s.window_reasons and s.onset.hold_z is not None]
    return float(np.sum(z) / np.sqrt(len(z))) if z else None


def step_echoes(ctx: AnalysisContext) -> list[StepEcho]:
    a_min = float(ctx.thresholds.param("echo", "a_min"))
    lo, hi = (float(x) for x in ctx.thresholds.param("echo", "delay_band_ms"))
    min_cos = float(ctx.thresholds.param(SPEC.check_id, "min_cosine"))
    order_snr = float(ctx.thresholds.param(SPEC.check_id, "order_min_snr"))
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
        strong = resp is not None and resp.cosine is not None and resp.magnitude >= order_snr * resp.threshold
        window = ctx.quality.windows.get(step.step_id)
        out.append(StepEcho(step.step_id, e.painted_t_ms, onset, resp, answered, order_ok, strong=strong,
                            window_reasons=window.blocking() if window is not None else []))
    # Silent only with the power to hear an echo: the session's own answered echoes, else the provisional cap.
    amps = [s.onset.amplitude for s in out if s.answered and not s.window_reasons and s.onset.amplitude is not None]
    hear = float(ctx.thresholds.param(SPEC.check_id, "max_silent_threshold"))
    if amps:
        hear = min(hear, 0.5 * float(np.median(amps)))
    faint = (z := faint_echo_z(out)) is not None and z >= float(ctx.thresholds.param(SPEC.check_id, "faint_echo_z"))
    for s in out:
        if s.answered and not s.order_ok and not s.strong:
            s.unclear = "weak_colour"  # an echo, but too small a colour change to read its direction
        elif s.silent and not (s.onset.threshold is not None and s.onset.threshold <= hear):
            s.unclear = "noisy"
        elif s.silent and faint:
            s.unclear = "faint"  # the face answered, below the onset threshold: weak light, not a recording
        s.clear = s.unclear is None
    return out


def _plot(steps: list[StepEcho], markers: list[tuple[float, str]]) -> Plot:
    points = sorted((s.painted + float(tr), float(v)) for s in steps if s.onset.valid
                    for tr, v in zip(s.onset.t_rel, s.onset.p, strict=True))
    step = max(1, int(np.ceil(len(points) / MAX_PLOT_POINTS)))
    return Plot(kind="echo", series={"face": points[::step]}, markers=markers)


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    if light_not_run(ctx):
        return []
    if (gate := session_abstain(ctx, SPEC, "time the light response")) is not None:
        return [gate]

    steps = step_echoes(ctx)
    valid = [s for s in steps if s.valid]
    judged = [s for s in steps if s.onset.valid and not s.window_reasons]
    unclear = sum(not s.clear for s in judged)
    poor = [s for s in steps if s.window_reasons]
    min_steps = int(ctx.thresholds.param(SPEC.check_id, "min_steps"))
    quality = len(valid) / len(steps)
    faint_z = faint_echo_z(steps)
    if len(valid) < min_steps:
        window_reasons = sorted({r for s in poor for r in s.window_reasons})
        why = "".join(f"; {n} {what}" for n, what in (
            (sum(s.unclear == "noisy" for s in judged), "were too noisy to tell an echo from silence"),
            (sum(s.unclear == "faint" for s in judged), "answered too faintly to time (weak light, not silence)"),
            (sum(s.unclear == "weak_colour" for s in judged), "changed too little to read the colour"),
        ) if n)
        if poor:
            what = ", ".join(reason_text(r).rstrip(".").lower() for r in window_reasons)
            why += f"; {len(poor)} had poor capture ({what})"
        return [abstain(SPEC, ["light.too_few_steps"] + ["light.weak_face_echo"] * (unclear > 0) + window_reasons,
                        f"Only {len(valid)} of {len(steps)} colour steps could be judged on the face (need "
                        f"{min_steps}){why}.", quality=quality,
                        features={"steps_valid": len(valid), "steps_shown": len(steps), "steps_unclear": unclear,
                                  "steps_poor_quality": len(poor), "faint_echo_z": faint_z},
                        window_id="all")]

    answered = [s for s in valid if s.answered]
    n_ok = sum(s.ok for s in valid)
    n_wrong = sum(s.wrong_order for s in valid)
    n_silent = sum(not s.ok and not s.wrong_order for s in valid)
    risk = 1.0 - n_ok / len(valid)
    flag_at = ctx.thresholds.flag_at(SPEC.check_id)
    lo, hi = (float(x) for x in ctx.thresholds.param("echo", "delay_band_ms"))
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
            SPEC, ctx.thresholds,
            risk=risk,
            quality=quality,
            features={
                "steps_valid": len(valid),
                "steps_answered": len(answered),
                "steps_order_ok": sum(s.order_ok for s in valid),
                "median_delay_ms": delay,
                "median_snr": float(np.median(snrs)) if snrs else None,
                "steps_unclear": unclear,
                "steps_poor_quality": len(poor),
                "faint_echo_z": faint_z,
            },
            reasons=reasons,
            explanation=explanation,
            window_id="all",
            plot=_plot([s for s in steps if s.onset.valid], [(s.painted, s.step_id) for s in steps]),
        )
    ]
