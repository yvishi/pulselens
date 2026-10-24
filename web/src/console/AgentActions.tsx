import { useState } from "react";
import { createSession, postAgentDecision } from "../api/client";
import { CustomerLink, customerLink } from "./NewSession";
import type { AgentAction, AgentDecision, Product } from "../contracts";

const LABEL: Record<AgentAction, string> = { approve: "Approve", reverify: "Re-verify", escalate: "Escalate to fraud" };
const DONE: Record<AgentAction, string> = { approve: "Approved", reverify: "Re-verification requested", escalate: "Escalated to fraud" };

interface Props {
  sessionId: string;
  product: Product;
  passcode: string;
  hasDecision: boolean;
  recorded: AgentDecision | null;
  onRecorded: () => void;
}

/** The agent's call. Re-verify also creates the next attempt and shows its customer link. */
export function AgentActions({ sessionId, product, passcode, hasDecision, recorded, onRecorded }: Props) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [at, setAt] = useState<string | null>(null);

  const act = async (action: AgentAction) => {
    setBusy(true);
    setError(null);
    try {
      await postAgentDecision(sessionId, passcode, { action, note });
      setAt(new Date().toLocaleTimeString());
      if (action === "reverify") {
        const next = await createSession({ product, previous_session_id: sessionId });
        setLink(customerLink(window.location.origin, next.customer_url));
      }
      onRecorded();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="actions" aria-label="Agent actions">
      <h3>Agent decision</h3>
      {recorded && (
        <p className="recorded" role="status">
          {DONE[recorded.action]}
          {at ? ` at ${at}` : ""}
          {recorded.note ? `: "${recorded.note}"` : ""}
        </p>
      )}
      <label>
        Note
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
      </label>
      <div className="buttons">
        {(Object.keys(LABEL) as AgentAction[]).map((a) => (
          <button key={a} type="button" className={`action-${a}`} disabled={!hasDecision || busy} onClick={() => void act(a)}>
            {LABEL[a]}
          </button>
        ))}
      </div>
      {!hasDecision && <p className="muted">Actions open when the analysis has finished.</p>}
      {link && (
        <div>
          New attempt for the customer:
          <CustomerLink url={link} />
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
