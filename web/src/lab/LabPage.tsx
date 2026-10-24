// The Lab recording page at /lab: operator form -> createSession({ label }) -> hand the device over -> the same
// capture screens a customer sees (CaptureFlow, no scores) -> "Recording saved" with the session id.
import { useState } from "react";
import { Link } from "react-router-dom";
import { createSession } from "../api/client";
import type { Label } from "../contracts";
import { CaptureFlow } from "../customer/CaptureFlow";
import "../customer/customer.css";
import { ErrorStep } from "../customer/steps/ErrorStep";
import { KIND_TEXT, LIGHT_TEXT, loadLastForm, saveLastForm, SET_TEXT, type LabelForm } from "./label";
import "./lab.css";
import { OperatorForm } from "./OperatorForm";

type Stage = "form" | "handoff" | "capture";

interface Recording {
  sessionId: string;
  token: string;
  label: Label;
}

/** Copies the session id; says "Copied" for a moment. Clipboard may be unavailable (http, old browser): then it says so. */
function CopyId({ id }: { id: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(id);
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2000);
  };
  return (
    <button type="button" className="btn" onClick={() => void copy()}>
      {state === "copied" ? "Copied" : state === "failed" ? "Copy not available: select the id" : "Copy id"}
    </button>
  );
}

export function LabPage() {
  const [stage, setStage] = useState<Stage>("form");
  const [form, setForm] = useState<LabelForm>(loadLastForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rec, setRec] = useState<Recording | null>(null);

  const begin = async (label: Label) => {
    setBusy(true);
    setError(null);
    try {
      const created = await createSession({ label });
      setRec({ sessionId: created.session_id, token: created.customer_token, label });
      setStage("handoff"); // unmounts the previous CaptureFlow, which disposes its session
    } catch (e) {
      setError(`Could not create the session: ${e instanceof Error ? e.message : String(e)}`);
      setStage("form");
    } finally {
      setBusy(false);
    }
  };

  const submit = (label: Label, values: LabelForm) => {
    setForm(values);
    saveLastForm(values);
    void begin(label);
  };

  const changeSettings = () => {
    setRec(null);
    setStage("form");
  };

  const operatorActions = rec && (
    <div className="lab-actions">
      <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void begin(rec.label)}>
        Record another (same settings)
      </button>
      <button type="button" className="btn" onClick={changeSettings}>Change settings</button>
    </div>
  );

  if (stage === "capture" && rec) {
    return (
      <CaptureFlow
        key={rec.sessionId}
        sessionId={rec.sessionId}
        token={rec.token}
        className="lab"
        data={{ "data-stage": stage }}
        renderResult={() => (
          <section className="lab-saved card" aria-labelledby="saved-title" lang="en">
            <h1 id="saved-title">Recording saved</h1>
            <p className="muted">Hand the device back to the operator. Session id:</p>
            <p className="lab-session-id" data-testid="lab-session-id">{rec.sessionId}</p>
            <div className="lab-saved-tools">
              <CopyId id={rec.sessionId} />
              <Link to={`/console/${rec.sessionId}`} className="lab-console-link">View it in the agent console</Link>
            </div>
            {operatorActions}
          </section>
        )}
        renderError={({ error }, lang) => (
          <>
            <ErrorStep lang={lang} error={error} />
            <div className="lab-saved card" lang="en">
              <p className="muted">
                Session id <span className="mono">{rec.sessionId}</span> (not complete)
              </p>
              {operatorActions}
            </div>
          </>
        )}
      />
    );
  }

  return (
    <main className="customer lab shell-page" data-stage={stage} lang="en">
      {stage === "form" && <OperatorForm initial={form} busy={busy} error={error} onSubmit={submit} />}

      {stage === "handoff" && rec && (
        <section className="lab-handoff card" aria-labelledby="handoff-title">
          <p className="eyebrow">Ready to record</p>
          <h1 id="handoff-title">Hand the device to the person</h1>
          <p className="lab-handoff-lead">
            They will see the same screens a customer sees and follow them on their own. Stay nearby, but do not help.
          </p>
          <ul className="lab-summary" aria-label="This recording">
            <li className="chip tone-stamp mono">{rec.label.person}</li>
            <li className="chip mono">{rec.label.device}</li>
            <li className="chip">{KIND_TEXT[rec.label.kind]}</li>
            {rec.label.tool && <li className="chip mono">{rec.label.tool}</li>}
            <li className="chip">{LIGHT_TEXT[rec.label.light]}</li>
            <li className="chip">Set {SET_TEXT[rec.label.set]}</li>
          </ul>
          <div className="lab-actions">
            <button type="button" className="btn btn-primary btn-big" onClick={() => setStage("capture")}>
              The person has the device
            </button>
            <button type="button" className="btn btn-quiet" onClick={changeSettings}>Back to the form</button>
          </div>
        </section>
      )}
    </main>
  );
}
