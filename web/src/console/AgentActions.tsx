import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { createSession, postAgentDecision } from "../api/client";
import type { AgentAction, AgentDecision, Outcome, Product, StepUp } from "../contracts";
import { CustomerLink, customerLink } from "./NewSession";

const ACTIONS: AgentAction[] = ["approve", "reverify", "escalate"];
const LABEL: Record<AgentAction, string> = { approve: "Approve", reverify: "Re-verify", escalate: "Escalate to fraud" };
const DONE: Record<AgentAction, string> = { approve: "Approved", reverify: "Re-verification requested", escalate: "Escalated to fraud" };
const WHAT: Record<AgentAction, string> = {
  approve: "Continue the KYC.",
  reverify: "Send the customer a new link to try again.",
  escalate: "Pass this customer to the fraud team.",
};
const BUTTON: Record<AgentAction, string> = { approve: "btn-ok", reverify: "btn-warn", escalate: "btn-stop" };

/** The button that matches the recommendation. HUMAN_REVIEW has none: the agent must look first. */
const SUGGESTED: Partial<Record<Outcome, AgentAction>> = { PASS: "approve", RETRY_STEP_UP: "reverify" };

/** Only these step-ups are fixed by a new customer link; the others are done by the agent or the bank. */
const REVERIFY_STEP_UPS: StepUp[] = ["fresh_challenge", "no_flash"];

interface Props {
  sessionId: string;
  product: Product;
  passcode: string;
  hasDecision: boolean;
  recorded: AgentDecision | null;
  onRecorded: () => void;
  /** the recommendation, to highlight the matching button */
  outcome?: Outcome | null;
  /** the suggested step-up: decides whether Re-verify is suggested and whether the next attempt skips the flash */
  stepUp?: StepUp | null;
  /** the customer asked for no flashing light: every new link they get keeps that */
  customerNoFlash?: boolean;
  /** the live-question ticks, appended to the saved note */
  checksNote?: string;
}

/** The agent's call. Re-verify also creates the next attempt and shows its customer link. */
export function AgentActions({ sessionId, product, passcode, hasDecision, recorded, onRecorded, outcome, stepUp, customerNoFlash, checksNote }: Props) {
  const id = useId();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState<{ url: string; sessionId: string | null } | null>(null);
  const [at, setAt] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const escalateRef = useRef<HTMLButtonElement>(null);
  const base = outcome ? SUGGESTED[outcome] : undefined;
  const suggested = base === "reverify" && !(stepUp && REVERIFY_STEP_UPS.includes(stepUp)) ? undefined : base;

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  const act = async (action: AgentAction) => {
    setBusy(true);
    setError(null);
    setConfirming(false);
    try {
      await postAgentDecision(sessionId, passcode, { action, note: checksNote ? [note.trim(), checksNote].filter(Boolean).join("\n") : note });
      setAt(new Date().toLocaleTimeString());
      if (action === "reverify") {
        const created = await createSession({ product, previous_session_id: sessionId, no_flash: stepUp === "no_flash" || Boolean(customerNoFlash) });
        setNext({ url: customerLink(window.location.origin, created.customer_url), sessionId: created.session_id ?? null });
      }
      onRecorded();
    } catch (e) {
      setError(`Your decision was not saved: ${e instanceof Error ? e.message : String(e)}. Please try again.`);
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setConfirming(false);
    escalateRef.current?.focus();
  };

  return (
    <section className="decide actions card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Your decision</h2>
      {recorded ? (
        <p className="recorded" role="status">
          {DONE[recorded.action]}
          {at ? ` at ${at}` : ""}
          {recorded.note ? `: "${recorded.note}"` : ""}
        </p>
      ) : (
        <p className="decide-hint">
          {!hasDecision
            ? "You can decide once the analysis has finished."
            : suggested
              ? `PulseLens suggests ${LABEL[suggested]}. You make the final call.`
              : "Review carefully, ask questions, then choose."}
        </p>
      )}

      <div className="note-field">
        <label htmlFor={`${id}-note`}>Note</label>
        <span id={`${id}-note-hint`} className="muted">
          Optional, saved with your decision.
        </span>
        <textarea id={`${id}-note`} aria-describedby={`${id}-note-hint`} value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
      </div>

      <ul className="choices">
        {ACTIONS.map((a) => {
          const isSuggested = hasDecision && a === suggested;
          return (
            <li key={a} className={`choice${isSuggested ? " is-suggested" : ""}`}>
              <button ref={a === "escalate" ? escalateRef : undefined} type="button"
                className={`btn ${BUTTON[a]} choice-btn action-${a}`} disabled={!hasDecision || busy || confirming}
                aria-describedby={`${id}-${a}`} onClick={() => (a === "escalate" ? setConfirming(true) : void act(a))}>
                {LABEL[a]}
              </button>
              <p id={`${id}-${a}`} className="choice-what">
                {isSuggested && <span className="chip tone-stamp">Suggested</span>} {WHAT[a]}
              </p>
            </li>
          );
        })}
      </ul>

      {confirming && (
        <div className="confirm" role="group" aria-labelledby={`${id}-confirm`}>
          <p id={`${id}-confirm`}>
            <strong>Escalate this customer to the fraud team?</strong>
          </p>
          <div className="confirm-buttons">
            <button ref={confirmRef} type="button" className="btn btn-stop" disabled={busy} onClick={() => void act("escalate")}>
              Confirm
            </button>
            <button type="button" className="btn btn-quiet" onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {next && (
        <div className="next-attempt">
          <h3>New link for the customer</h3>
          <p className="muted">Share this link or QR code with the customer on the call.</p>
          <CustomerLink url={next.url} />
          {next.sessionId && (
            <p>
              <Link to={`/console/${next.sessionId}`} className="btn btn-primary">
                Watch the new attempt
              </Link>
            </p>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
