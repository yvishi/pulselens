"""sensor.mode_probe (family B, B.probe): what the camera did when the preflight asked it to switch modes
(Preflight.probe, Yash's capture/probe.ts). Ported from the old camera.modes check, on the new ModeProbe rows.

Each row asks for an exact size (resizeMode "none"): refused (accepted false; also when the browser cannot ask),
or accepted with the size actually delivered, the time to the first frame at the new size (null: none within 1 s)
and the frames missing during the switch. A real sensor refuses odd modes or reconfigures slowly and loses frames;
software rescales anything at once.
- Phantom switch, risk 1 (`sensor.phantom_switch`, ported rule): a mode was accepted, but no frame of the new size
  arrived and the video stayed at the working size. Settings that change while the frames do not.
- Too perfect, risk 0.7 (`sensor.probe_too_perfect`): the unusual 1000x750 mode was accepted, delivered at that
  size within 150 ms and with no missing frame. The old repo measured exactly this on Chromium's fake camera, while
  a real webcam refused the mode. **A hypothesis for OBS and other virtual cameras: measure it at S2.**
Abstains when the probe did not run (Safari, Firefox: no resizeMode) or no mode was accepted (unsupported, never
failed).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult

SPEC = specs.SENSOR_MODE_PROBE


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    pf = ctx.bundle.preflight
    rows = list(pf.probe) if pf is not None else []
    if not rows:
        return [abstain(SPEC, ["sensor.probe_not_run"], "The mode-switch probe did not run in this browser, so it is "
                        "recorded as unsupported, not failed.", window_id="all")]
    accepted = [r for r in rows if r.accepted]
    if not accepted:
        return [abstain(SPEC, ["sensor.probe_not_run"], f"The camera accepted none of the {len(rows)} exact modes "
                        "asked for, so it is recorded as unsupported, not failed.",
                        features={"requests": len(rows), "accepted": 0}, window_id="all")]

    unusual_size = tuple(int(x) for x in ctx.thresholds.param(SPEC.check_id, "unusual_size"))
    max_switch = float(ctx.thresholds.param(SPEC.check_id, "max_switch_ms"))
    working = (pf.width, pf.height)
    phantom = [r for r in accepted if r.switch_ms is None and r.delivered is not None
               and tuple(r.delivered) != tuple(r.requested[:2]) and tuple(r.delivered) == working]
    unusual = next((r for r in accepted if tuple(r.requested[:2]) == unusual_size), None)
    unusual_ok = unusual is not None and unusual.delivered is not None and tuple(unusual.delivered) == unusual_size
    switches = [float(r.switch_ms) for r in accepted if r.switch_ms is not None]
    too_perfect = (unusual_ok and unusual.switch_ms is not None and unusual.switch_ms < max_switch
                   and unusual.frames_missing == 0)
    features = {
        "requests": len(rows),
        "accepted": len(accepted),
        "accepted_unusual": float(unusual_ok),
        "unusual_switch_ms": unusual.switch_ms if unusual_ok else None,
        "median_switch_ms": float(np.median(switches)) if switches else None,
        "frames_missing_total": sum(r.frames_missing or 0 for r in accepted),
        "phantom_switches": len(phantom),
    }
    w, h = unusual_size
    if phantom:
        sizes = ", ".join(f"{r.requested[0]}x{r.requested[1]}" for r in phantom)
        risk, reasons = 1.0, ["sensor.phantom_switch"]
        explanation = (f"The camera accepted {sizes} but kept sending {working[0]}x{working[1]} frames: settings "
                       "that change while the video does not.")
    elif too_perfect:
        risk, reasons = 0.7, ["sensor.probe_too_perfect"]
        explanation = (f"The camera accepted the unusual {w}x{h} mode and switched in {unusual.switch_ms:.0f} ms "
                       f"with no missing frame (limit {max_switch:.0f} ms), as software that rescales video does; a "
                       "hypothesis for virtual cameras.")
    else:
        risk, reasons = 0.0, []
        how = (f"switched to the unusual {w}x{h} mode in {unusual.switch_ms:.0f} ms"
               if unusual_ok and unusual.switch_ms is not None
               else f"did not deliver the unusual {w}x{h} mode")
        explanation = f"The camera accepted {len(accepted)} of {len(rows)} modes and {how}, as a real sensor can."
    return [result(SPEC, ctx.thresholds, risk=risk, quality=1.0,
                   features=features, reasons=reasons, explanation=explanation, window_id="all")]
