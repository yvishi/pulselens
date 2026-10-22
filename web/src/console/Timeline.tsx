import type { Challenge, ChallengeEvent } from "../contracts";

const pct = (ms: number, total: number) => `${Math.max(0, Math.min(100, (ms / total) * 100))}%`;

/** Requested steps (top) and what the customer's screen actually showed (bottom), on one time axis. */
export function Timeline({ challenge, events }: { challenge: Challenge | null; events: ChallengeEvent[] }) {
  if (!challenge) return <p className="muted">No challenge was issued.</p>;
  const total = challenge.baseline_ms + challenge.total_ms;
  const byStep = new Map(events.map((e) => [e.step_id, e]));
  return (
    <section className="timeline" aria-label="Challenge timeline">
      <h3>Challenge timeline</h3>
      <div className="lane" aria-label="Requested">
        <span className="lane-label">Requested</span>
        <span className="baseline" style={{ left: 0, width: pct(challenge.baseline_ms, total) }} title="baseline" />
        {challenge.steps.map((s) => {
          const start = challenge.baseline_ms + s.start_offset_ms;
          const length = s.kind === "colour" ? s.dwell_ms : s.duration_ms;
          return s.kind === "colour" ? (
            <span key={s.step_id} className="step colour" title={`${s.step_id}: hue ${s.hue_deg}°`}
              style={{ left: pct(start, total), width: pct(length, total), background: `hsl(${s.hue_deg} 70% 60%)` }} />
          ) : (
            <span key={s.step_id} className="step turn" title={`${s.step_id}: turn ${s.direction}`}
              style={{ left: pct(start, total), width: pct(length, total) }}>
              {s.direction === "left" ? "←" : "→"}
            </span>
          );
        })}
      </div>
      <div className="lane" aria-label="Observed">
        <span className="lane-label">Observed</span>
        {challenge.steps.map((s) => {
          const e = byStep.get(s.step_id);
          if (!e) {
            return <span key={s.step_id} className="event missing" title={`${s.step_id}: no event`}
              style={{ left: pct(challenge.baseline_ms + s.start_offset_ms, total) }}>?</span>;
          }
          if (e.status === "skipped" || e.painted_t_ms === null) {
            return <span key={s.step_id} className="event skipped" title={`${s.step_id}: skipped (${e.skip_reason ?? "?"})`}
              style={{ left: pct(challenge.baseline_ms + s.start_offset_ms, total) }}>✕</span>;
          }
          return <span key={s.step_id} className="event shown" title={`${s.step_id}: painted at ${e.painted_t_ms.toFixed(0)} ms`}
            style={{ left: pct(e.painted_t_ms, total) }} />;
        })}
      </div>
      <p className="muted">
        {challenge.steps.length} steps over {(total / 1000).toFixed(1)} s, including a {(challenge.baseline_ms / 1000).toFixed(1)} s baseline;{" "}
        {events.filter((e) => e.status === "shown").length} shown, {events.filter((e) => e.status === "skipped").length} skipped.
      </p>
    </section>
  );
}
