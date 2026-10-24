import type { Challenge, ChallengeEvent } from "../contracts";

const pct = (ms: number, total: number) => `${Math.max(0, Math.min(100, (ms / total) * 100))}%`;

/** Why the customer's screen skipped a step, in plain words. */
const SKIP_PLAIN: Record<string, string> = {
  fps_drop: "the camera slowed down",
  no_flash: "flashing light was turned off",
  page_hidden: "the customer left the page",
};

const skipPlain = (reason: string | null | undefined) => (reason ? (SKIP_PLAIN[reason] ?? reason.replace(/_/g, " ")) : "no reason given");

/** Requested steps (top) and what the customer's screen actually showed (bottom), on one time axis. */
export function Timeline({ challenge, events }: { challenge: Challenge | null; events: ChallengeEvent[] }) {
  if (!challenge) return <p className="muted">The customer has not reached the challenge yet.</p>;
  const total = challenge.baseline_ms + challenge.total_ms;
  const byStep = new Map(events.map((e) => [e.step_id, e]));
  const shown = events.filter((e) => e.status === "shown").length;
  const skipped = events.filter((e) => e.status === "skipped");
  const reasons = [...new Set(skipped.map((e) => skipPlain(e.skip_reason)))];
  return (
    <section className="timeline" aria-label="Challenge timeline">
      <h3>What the customer's screen did</h3>
      <p className="timeline-summary">
        {shown} of {challenge.steps.length} steps shown, {skipped.length} skipped
        {reasons.length > 0 ? ` (${reasons.join("; ")})` : ""}.
      </p>
      <div className="lanes">
        <div className="lane-row">
          <span className="lane-label">Asked for</span>
          <div className="lane" aria-label="Requested">
            <span className="baseline" style={{ left: 0, width: pct(challenge.baseline_ms, total) }} title="baseline" />
            {challenge.steps.map((s) => {
              const start = challenge.baseline_ms + s.start_offset_ms;
              const length = s.kind === "colour" ? s.dwell_ms : s.duration_ms;
              return s.kind === "colour" ? (
                // The step's own hue: data, not decoration.
                <span key={s.step_id} className="step colour" title={`${s.step_id}: colour, hue ${s.hue_deg}°`}
                  style={{ left: pct(start, total), width: pct(length, total), background: `hsl(${s.hue_deg} 70% 60%)` }} />
              ) : (
                <span key={s.step_id} className="step turn" title={`${s.step_id}: turn ${s.direction}`}
                  style={{ left: pct(start, total), width: pct(length, total) }}>
                  <span aria-hidden="true">{s.direction === "left" ? "←" : "→"}</span>
                </span>
              );
            })}
          </div>
        </div>
        <div className="lane-row">
          <span className="lane-label">Shown</span>
          <div className="lane" aria-label="Observed">
            {challenge.steps.map((s) => {
              const e = byStep.get(s.step_id);
              const left = pct(challenge.baseline_ms + s.start_offset_ms, total);
              if (!e) {
                return <span key={s.step_id} className="event missing" title={`${s.step_id}: no report from the phone`} style={{ left }}>?</span>;
              }
              if (e.status === "skipped" || e.painted_t_ms === null) {
                return <span key={s.step_id} className="event skipped" title={`${s.step_id}: skipped (${skipPlain(e.skip_reason)})`}
                  style={{ left }}>✕</span>;
              }
              return <span key={s.step_id} className="event shown" title={`${s.step_id}: shown at ${e.painted_t_ms.toFixed(0)} ms`}
                style={{ left: pct(e.painted_t_ms, total) }} />;
            })}
          </div>
        </div>
      </div>
      <p className="muted timeline-legend">
        About {(total / 1000).toFixed(0)} seconds in all, starting with {(challenge.baseline_ms / 1000).toFixed(1)} s of
        stillness. Dots: shown on time; ✕: skipped; ?: not reported.
      </p>
    </section>
  );
}
