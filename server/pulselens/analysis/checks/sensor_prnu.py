"""sensor.prnu (family B, B.prnu): the sensor's fixed pixel pattern (PRNU), estimated on odd and even frames
separately and compared by PCE (vision/prnu.py). Ported from the old camera.fingerprint check.

**Supporting only: `flag` is always false** (`specs.SENSOR_PRNU.never_flags`). Chromium's fake camera produced a
stable pattern (PCE 97) and genuine webcams went as low as PCE 174 in the old repo, so the result is shown on the
console (risk 1 below PCE 50) and never votes.
"""

from __future__ import annotations

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.prnu import LUMA_RANGE, MIN_FRAMES
from pulselens.contracts import CheckResult

SPEC = specs.SENSOR_PRNU


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    fp = ctx.fingerprint
    if fp is None:
        return [abstain(SPEC, ["quality.too_few_frames"], f"Fewer than {MIN_FRAMES} frames with a mean brightness "
                        f"between {LUMA_RANGE[0]} and {LUMA_RANGE[1]} to estimate the sensor pattern.",
                        window_id="all")]
    limit = float(ctx.thresholds.param(SPEC.check_id, "min_pce"))
    low = fp.pce < limit
    explanation = (f"No stable sensor pattern: PCE {fp.pce:.1f} (limit {limit:.0f}) over {fp.frames} frames"
                   if low else
                   f"The sensor pattern in odd frames matches the even frames (PCE {fp.pce:.0f}, limit {limit:.0f})")
    explanation += "; supporting evidence only, never a flag."
    return [result(SPEC, ctx.thresholds, risk=1.0 if low else 0.0,
                   quality=min(1.0, fp.frames / (2 * MIN_FRAMES)),
                   features={"pce": fp.pce, "frames": fp.frames, "skipped": fp.skipped},
                   reasons=["sensor.prnu_weak"] if low else [], explanation=explanation, window_id="all")]
