"""Ingest integrity, service step 2 (docs/tasks/keshav.md K5): two results, both family B, vote group B.protocol.

- integrity.protocol: protocol_error when the capture broke the protocol (a hard rule, never a quality judgement).
- integrity.coverage: how much of the upload arrived. Network gaps are coverage, never a protocol error.
"""

from __future__ import annotations

from statistics import median

from pulselens.bundle import Bundle
from pulselens.contracts import CheckResult
from pulselens.engine.reason_text import reason_text
from pulselens.engine.results import abstain, protocol_error, usable
from pulselens.engine.steps import step_window

MIN_FRAMES = 50
FLAG_AT = 0.2  # share of missing upload batches


def _protocol(bundle: Bundle) -> CheckResult:
    codes: list[str] = []
    rows = [r for r in bundle.frame_rows if isinstance(r.get("idx"), int) and isinstance(r.get("t_ms"), int | float)]
    idxs = [r["idx"] for r in rows]
    if len(idxs) != len(set(idxs)):
        codes.append("integrity.duplicate_index")
    by_idx = sorted({r["idx"]: r["t_ms"] for r in rows}.items())
    if any(b <= a for (_, a), (_, b) in zip(by_idx, by_idx[1:], strict=False)):
        codes.append("integrity.non_monotonic_time")

    ch = bundle.challenge
    if ch is None:
        if bundle.frames:
            codes.append("integrity.no_challenge")
    else:
        order = {s.step_id: k for k, s in enumerate(ch.steps)}
        if any(e.step_id not in order for e in bundle.events):
            codes.append("integrity.unknown_step")
        shown = sorted(
            (e for e in bundle.events if e.status == "shown" and e.painted_t_ms is not None and e.step_id in order),
            key=lambda e: e.painted_t_ms,
        )
        positions = [order[e.step_id] for e in shown]
        if positions != sorted(positions):
            codes.append("integrity.event_order")
    if int(bundle.session.get("after_complete_attempts", 0)) > 0:
        codes.append("integrity.after_complete")

    if codes:
        return protocol_error("integrity.protocol", " ".join(reason_text(c) for c in codes), codes)
    return usable("integrity.protocol", f"Frames, events and the challenge follow the protocol "
                  f"({len(bundle.frames)} frames, {len(bundle.events)} challenge events).")


def _frames_per_step(bundle: Bundle) -> float | None:
    ch = bundle.challenge
    if ch is None or not ch.steps:
        return None
    events = {e.step_id: e for e in bundle.events}
    counts = []
    for s in ch.steps:
        w = step_window(ch, s, events.get(s.step_id))
        counts.append(sum(w.start_ms <= f.t_ms < w.end_ms for f in bundle.frames))
    return float(median(counts))


def _coverage(bundle: Bundle) -> CheckResult:
    n = len(bundle.frames)
    seqs = {r["batch_seq"] for r in bundle.frame_rows if isinstance(r.get("batch_seq"), int)}
    total_batches = max(seqs) + 1 if seqs else 0
    missing = total_batches - len(seqs)
    span = bundle.frames[-1].t_ms - bundle.frames[0].t_ms if n >= 2 else 0.0
    per_step = _frames_per_step(bundle)
    features = {"frames": float(n), "batch_gaps": float(missing), "span_ms": float(span)}
    if per_step is not None:
        features["frames_per_step_window"] = per_step
    if n < MIN_FRAMES:
        return abstain("integrity.coverage", f"Only {n} frames arrived (need {MIN_FRAMES}) to judge the upload.",
                       ["integrity.too_few_frames"], quality=n / MIN_FRAMES, features=features)
    risk = min(1.0, missing / total_batches) if total_batches else 0.0
    flag = risk >= FLAG_AT
    gaps = f"{missing} of {total_batches} upload batches missing" if missing else f"all {total_batches} upload batches"
    per = f", median {per_step:.0f} frames per challenge step" if per_step is not None else ""
    return usable("integrity.coverage", f"{n} frames over {span / 1000:.1f} s arrived, {gaps}{per}.", risk=risk,
                  flag=flag, features=features, reason_codes=["integrity.batch_gaps"] if flag else [])


def check_integrity(bundle: Bundle) -> list[CheckResult]:
    return [_protocol(bundle), _coverage(bundle)]
