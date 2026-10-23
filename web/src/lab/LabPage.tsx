// The Lab recording page at /lab: operator form -> createSession({ label }) -> hand the device over -> the same
// capture screens a customer sees (CaptureFlow, no scores) -> "Recording saved" with the session id.
import { useState } from "react";
import { createSession } from "../api/client";
import type { Label } from "../contracts";
import { CaptureFlow } from "../customer/CaptureFlow";
import "../customer/customer.css";
import { ErrorStep } from "../customer/steps/ErrorStep";
import { loadLastForm, saveLastForm, type LabelForm } from "./label";
import "./lab.css";
import { OperatorForm } from "./OperatorForm";

type Stage = "form" | "handoff" | "capture";

interface Recording {
  sessionId: string;
  token: string;
  label: Label;
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
    <div className="actions">
      <button type="button" className="primary" disabled={busy} onClick={() => void begin(rec.label)}>
        Record another (same settings)
      </button>
      <button type="button" onClick={changeSettings}>Change settings</button>
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
          <section className="step" aria-labelledby="saved-title" lang="en">
            <h1 id="saved-title">Recording saved</h1>
            <p className="muted">Session id</p>
            <p className="lab-session-id" data-testid="lab-session-id">{rec.sessionId}</p>
            {operatorActions}
          </section>
        )}
        renderError={({ detail }, lang) => (
          <>
            <ErrorStep lang={lang} detail={detail} />
            <div lang="en">
              <p className="muted">Session id {rec.sessionId} (not complete)</p>
              {operatorActions}
            </div>
          </>
        )}
      />
    );
  }

  return (
    <main className="customer lab" data-stage={stage} lang="en">
      {stage === "form" && <OperatorForm initial={form} busy={busy} error={error} onSubmit={submit} />}

      {stage === "handoff" && rec && (
        <section className="step" aria-labelledby="handoff-title">
          <h1 id="handoff-title">Hand the device to the person</h1>
          <p className="lab-summary">
            {rec.label.person} · {rec.label.device} · {rec.label.kind}
            {rec.label.tool ? ` (${rec.label.tool})` : ""} · {rec.label.light} · set {rec.label.set}
          </p>
          <p className="muted">They will see the same screens a customer sees.</p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => setStage("capture")}>
              The person has the device
            </button>
            <button type="button" onClick={changeSettings}>Back to the form</button>
          </div>
        </section>
      )}
    </main>
  );
}
