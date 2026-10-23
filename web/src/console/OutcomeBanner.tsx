import type { Decision, Outcome } from "../contracts";

export const OUTCOME_TITLE: Record<Outcome, string> = {
  PASS: "PASS",
  RETRY_STEP_UP: "RETRY / STEP-UP",
  HUMAN_REVIEW: "HUMAN REVIEW",
};

/** The recommendation, its reasons and the step-up. PulseLens recommends; the agent decides. */
export function OutcomeBanner({ decision }: { decision: Decision | null }) {
  if (!decision) {
    return (
      <section className="banner banner-pending" aria-label="Outcome" aria-busy="true">
        <h2>Analysing…</h2>
        <p>The recommendation appears here when the analysis finishes.</p>
      </section>
    );
  }
  return (
    <section className={`banner outcome-${decision.outcome}`} aria-label="Outcome">
      <h2>{OUTCOME_TITLE[decision.outcome]}</h2>
      <ul>
        {decision.reasons.map((r, k) => (
          <li key={k}>{r}</li>
        ))}
      </ul>
      <p className="decides">PulseLens recommends; the agent decides.</p>
    </section>
  );
}
