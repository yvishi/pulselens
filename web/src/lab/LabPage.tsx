// The Lab recording page at /lab: operator form -> createSession({ label }) -> hand the device over -> the same
// CaptureSession flow and customer screens (no scores) -> "Recording saved" with the session id.
import { useEffect, useRef, useState } from "react";
import { createSession } from "../api/client";
import { CaptureSession, type CaptureState } from "../capture/session";
import type { Label } from "../contracts";
import "../customer/customer.css";
import { Consent } from "../customer/steps/Consent";
import { ErrorStep } from "../customer/steps/ErrorStep";
import { Status } from "../customer/steps/Status";
import { t, turnKey, type Lang } from "../customer/strings";
import { loadLastForm, saveLastForm, type LabelForm } from "./label";
import "./lab.css";
import { OperatorForm } from "./OperatorForm";

/** Phases where the camera is open and the <video> must stay rendered (the grabber reads it). */
const CAMERA_PHASES = new Set(["camera", "preflight", "coaching", "ready", "challenge"]);

type Stage = "form" | "handoff" | "capture";

interface Recording {
  sessionId: string;
  token: string;
  label: Label;
}

export function LabPage() {
  const lang: Lang = "en";
  const [stage, setStage] = useState<Stage>("form");
  const [form, setForm] = useState<LabelForm>(loadLastForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rec, setRec] = useState<Recording | null>(null);
  const [state, setState] = useState<CaptureState>({ phase: "consent" });
  const video = useRef<HTMLVideoElement>(null);
  const session = useRef<CaptureSession | null>(null);

  useEffect(() => () => session.current?.dispose(), []);

  const begin = async (label: Label) => {
    session.current?.dispose();
    session.current = null;
    setBusy(true);
    setError(null);
    try {
      const created = await createSession({ label });
      setRec({ sessionId: created.session_id, token: created.customer_token, label });
      setState({ phase: "consent" });
      setStage("handoff");
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

  const start = (noFlashRequested: boolean) => {
    if (session.current || !video.current || !rec) return;
    const s = new CaptureSession({
      sessionId: rec.sessionId, token: rec.token, video: video.current, overlayRoot: document.body, onState: setState,
      turnText: (dir) => t(turnKey(dir), lang),
    });
    session.current = s;
    void s.start(noFlashRequested); // called inside the click: the overlay may ask for fullscreen
  };

  const changeSettings = () => {
    session.current?.dispose();
    session.current = null;
    setRec(null);
    setStage("form");
  };

  const { phase, detail } = state;
  const capturing = stage === "capture";
  const operatorActions = rec && (
    <div className="actions">
      <button type="button" className="primary" disabled={busy} onClick={() => void begin(rec.label)}>
        Record another (same settings)
      </button>
      <button type="button" onClick={changeSettings}>Change settings</button>
    </div>
  );

  return (
    <main className="customer lab" data-stage={stage} data-phase={capturing ? phase : undefined}>
      <video
        ref={video}
        className={capturing && CAMERA_PHASES.has(phase) ? `selfview selfview-${phase === "challenge" ? "hidden" : "shown"}` : "selfview-off"}
        muted
        playsInline
        aria-hidden="true"
      />
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

      {capturing && phase === "consent" && <Consent lang={lang} onStart={start} />}
      {capturing && phase === "camera" && <Status lang={lang} text="camera.asking" />}
      {capturing && (phase === "preflight" || phase === "coaching" || phase === "ready") && (
        <Status lang={lang} text="preflight.checking" hint="preflight.hint" />
      )}
      {capturing && phase === "challenge" && <Status lang={lang} text="challenge.look" />}
      {capturing && (phase === "uploading" || phase === "waiting") && <Status lang={lang} text="waiting.text" />}

      {capturing && phase === "result" && rec && (
        <section className="step" aria-labelledby="saved-title">
          <h1 id="saved-title">Recording saved</h1>
          <p className="muted">Session id</p>
          <p className="lab-session-id" data-testid="lab-session-id">{rec.sessionId}</p>
          {operatorActions}
        </section>
      )}
      {capturing && phase === "error" && rec && (
        <>
          <ErrorStep lang={lang} detail={detail} />
          <p className="muted">Session id {rec.sessionId} (not complete)</p>
          {operatorActions}
        </>
      )}
    </main>
  );
}
