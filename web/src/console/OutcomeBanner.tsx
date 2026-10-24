import type { ReactNode } from "react";
import type { Decision, Outcome, SessionState, StepUp } from "../contracts";
import { OUTCOME_PLAIN } from "./plain";

/** The system's own code for each outcome. The list page shows it; the verdict shows it as secondary text. */
export const OUTCOME_TITLE: Record<Outcome, string> = {
  PASS: "PASS",
  RETRY_STEP_UP: "RETRY / STEP-UP",
  HUMAN_REVIEW: "HUMAN REVIEW",
};

/** The step-up the engine suggests, as an instruction the agent can follow. */
export const STEP_UP_PLAIN: Record<StepUp, string> = {
  fresh_challenge: "Send a new link for a fresh check.",
  no_flash: "Send a new link without flashing light.",
  agent_checks: "Ask the live questions in the decision panel and check their documents.",
  assisted_kyc: "Follow the bank's assisted-KYC process (branch or business correspondent).",
};

/**
 * The recommendation as a verdict stamp: the plain verdict, what to do next and why. PulseLens recommends; the
 * agent decides. `notes` (the honesty labels) sit under the reasons so they are read with the verdict.
 */
/** What the panel says before there is a verdict, by session state: the customer may not have started yet. */
const WAITING: Partial<Record<SessionState, { title: string; body: string; hint: string }>> = {
  created: {
    title: "Waiting for customer",
    body: "The customer has not opened the link yet.",
    hint: "Share the link or QR code, and ask them to open it on their phone.",
  },
  preflight: {
    title: "Check in progress",
    body: "The customer is getting their camera ready.",
    hint: "Keep the customer on the call.",
  },
  capturing: {
    title: "Check in progress",
    body: "The customer is doing the check now. It takes about 20 seconds.",
    hint: "Keep the customer on the call.",
  },
  expired: {
    title: "Link expired",
    body: "This link expired before the check finished.",
    hint: "Start a new verification from the Verifications page.",
  },
};

const ANALYSING = {
  title: "Analysing…",
  body: "The recommendation appears here when the analysis finishes. This usually takes a few seconds.",
  hint: "Keep the customer on the call until then.",
};

export function OutcomeBanner({ decision, state, notes }: { decision: Decision | null; state?: SessionState; notes?: ReactNode }) {
  if (!decision) {
    const w = (state && WAITING[state]) ?? ANALYSING;
    return (
      <section className="verdict verdict-pending card" aria-label="Outcome" aria-busy="true">
        <p className="eyebrow">PulseLens recommendation</p>
        <div className="verdict-top">
          <div className="stamp stamp-pending">
            <h2>{w.title}</h2>
          </div>
          <div className="verdict-next">
            <p>{w.body}</p>
            <p className="muted">{w.hint}</p>
          </div>
        </div>
        {notes}
      </section>
    );
  }

  const plain = OUTCOME_PLAIN[decision.outcome];
  return (
    <section className={`verdict verdict-${plain.tone} card`} aria-label="Outcome">
      <p className="eyebrow">PulseLens recommendation</p>
      <div className="verdict-top">
        <div className="stamp-block">
          <div className="stamp">
            <h2>{plain.title}</h2>
          </div>
          <p className="verdict-code muted">
            System code: <span className="mono">{OUTCOME_TITLE[decision.outcome]}</span>
          </p>
        </div>
        <div className="verdict-next">
          <h3>What to do next</h3>
          <p className="next-text">{plain.next}</p>
          {decision.step_up && (
            <p className="step-up">
              <strong>Suggested step:</strong> {STEP_UP_PLAIN[decision.step_up]}
            </p>
          )}
        </div>
      </div>
      {decision.reasons.length > 0 && (
        <div className="verdict-why">
          <h3>Why</h3>
          <ul>
            {decision.reasons.map((r, k) => (
              <li key={k}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="decides">PulseLens recommends; the agent decides.</p>
      {notes}
    </section>
  );
}
