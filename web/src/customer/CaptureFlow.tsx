// The capture screens shared by the customer page and the Lab page: the <video>, the CaptureSession wiring (overlay,
// ring turn prompt, language) and the phase -> screen mapping. CaptureSession drives everything; this only renders it.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { startTap, type DeviceSession } from "../capture/device";
import { CaptureSession, type CaptureState } from "../capture/session";
import "./customer.css";
import { CameraIcon, FaceInFrame, LockIcon, WeakSignalIcon } from "./steps/Art";
import { Coaching } from "./steps/Coaching";
import { Consent, LangToggle } from "./steps/Consent";
import { ErrorStep } from "./steps/ErrorStep";
import { cardDigitPrompt, cardNodPrompt } from "./steps/LivePrompts";
import { Progress, stepOf } from "./steps/Progress";
import { Result } from "./steps/Result";
import { Status, Waiting } from "./steps/Status";
import { ringTurnPrompt } from "./steps/TurnPrompt";
import { browserLang, t, turnKey, type Lang } from "./strings";

/** Phases where the camera is open and the <video> must stay rendered (the grabber reads it). */
const CAMERA_PHASES = new Set(["camera", "preflight", "coaching", "ready", "challenge"]);
/** Phases where frames are still going out, so "Weak connection, still sending…" applies. */
const WEAK_PHASES = new Set(["challenge", "uploading", "waiting"]);

export interface CaptureFlowProps {
  sessionId: string;
  /** the customer token; empty shows the "no_token" error screen */
  token: string;
  /** extra classes on <main> (always has "customer") */
  className?: string;
  /** extra data-* attributes on <main> */
  data?: Record<`data-${string}`, string | undefined>;
  /** replaces the default result screen (the CustomerStatus message) */
  renderResult?: (state: Extract<CaptureState, { phase: "result" }>, lang: Lang) => ReactNode;
  /** replaces the default error screen */
  renderError?: (state: Extract<CaptureState, { phase: "error" }>, lang: Lang) => ReactNode;
}

/**
 * One capture: consent (Start or no-flash, the user gesture that starts the session and may ask for fullscreen),
 * camera, preflight, coaching, challenge, waiting, then result or error. Mount it with `key={sessionId}` to start over;
 * unmounting disposes the session.
 */
export function CaptureFlow({ sessionId, token, className, data, renderResult, renderError }: CaptureFlowProps) {
  const [lang, setLang] = useState<Lang>(browserLang);
  const [state, setState] = useState<CaptureState>(
    token ? { phase: "consent" } : { phase: "error", error: "no_token" },
  );
  const video = useRef<HTMLVideoElement>(null);
  const session = useRef<CaptureSession | null>(null);
  const device = useRef<DeviceSession | null>(null);

  useEffect(
    () => () => {
      session.current?.dispose();
      device.current?.release();
    },
    [],
  );
  // The session is over: give back the wake lock and leave fullscreen.
  useEffect(() => {
    if (state.phase === "result" || state.phase === "error") device.current?.release();
  }, [state.phase]);

  const start = (noFlashRequested: boolean) => {
    if (session.current || !video.current) return;
    device.current = startTap(); // first, synchronously inside the click: fullscreen, wake lock, iOS motion prompt
    const s = new CaptureSession({
      sessionId, token, video: video.current, overlayRoot: document.body, onState: setState,
      turnText: (dir) => t(turnKey(dir), lang),
      turnPrompt: ringTurnPrompt(),
      nodText: () => t("nod.prompt", lang),
      digitText: () => t("digit.prompt", lang),
      nodPrompt: cardNodPrompt(),
      digitPrompt: cardDigitPrompt(),
    });
    session.current = s;
    void s.start(noFlashRequested); // called inside the click: the overlay may ask for fullscreen
  };

  const { phase, tips, agentQuestions, weakConnection } = state;
  const step = stepOf(phase);
  return (
    <main className={className ? `customer ${className}` : "customer"} data-phase={phase} lang={lang} {...data}>
      <video
        ref={video}
        className={CAMERA_PHASES.has(phase) ? `selfview selfview-${phase === "challenge" ? "hidden" : "shown"}` : "selfview-off"}
        muted
        playsInline
        aria-hidden="true"
      />
      <header className="kyc-head">
        <p className="kyc-secure">
          <LockIcon />
          <span>{t("frame.secure", lang)}</span>
        </p>
        {phase === "consent" && <LangToggle lang={lang} onLang={setLang} />}
      </header>
      {step !== null && <Progress lang={lang} step={step} complete={phase === "result"} />}
      <div className="kyc-body">
        {phase === "consent" && <Consent lang={lang} onStart={start} />}
        {phase === "camera" && <Status lang={lang} text="camera.asking" art={<CameraIcon />} />}
        {phase === "coaching" && <Coaching lang={lang} tips={tips} />}
        {(phase === "preflight" || phase === "ready") && (
          <Status lang={lang} text="preflight.checking" hint="preflight.hint" art={<FaceInFrame />} />
        )}
        {phase === "challenge" && <Status lang={lang} text="challenge.look" />}
        {(phase === "uploading" || phase === "waiting") && (
          <Status lang={lang} text="waiting.text" hint={agentQuestions ? "agent.questions" : undefined} art={<Waiting />} />
        )}
        {weakConnection && WEAK_PHASES.has(phase) && (
          <p className="weak-connection" role="status" aria-live="polite">
            <WeakSignalIcon />
            <span>{t("upload.weak", lang)}</span>
          </p>
        )}
        {state.phase === "result" &&
          (renderResult ? renderResult(state, lang) : <Result lang={lang} message={state.message} agentQuestions={agentQuestions} />)}
        {state.phase === "error" && (renderError ? renderError(state, lang) : <ErrorStep lang={lang} error={state.error} />)}
      </div>
    </main>
  );
}
