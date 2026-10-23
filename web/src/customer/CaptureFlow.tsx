// The capture screens shared by the customer page and the Lab page: the <video>, the CaptureSession wiring (overlay,
// ring turn prompt, language) and the phase -> screen mapping. CaptureSession drives everything; this only renders it.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { startTap, type DeviceSession } from "../capture/device";
import { CaptureSession, type CaptureState } from "../capture/session";
import "./customer.css";
import { Coaching } from "./steps/Coaching";
import { Consent } from "./steps/Consent";
import { ErrorStep } from "./steps/ErrorStep";
import { Result } from "./steps/Result";
import { Status } from "./steps/Status";
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
  renderResult?: (state: CaptureState, lang: Lang) => ReactNode;
  /** replaces the default error screen */
  renderError?: (state: CaptureState, lang: Lang) => ReactNode;
}

/**
 * One capture: consent (Start or no-flash, the user gesture that starts the session and may ask for fullscreen),
 * camera, preflight, coaching, challenge, waiting, then result or error. Mount it with `key={sessionId}` to start over;
 * unmounting disposes the session.
 */
export function CaptureFlow({ sessionId, token, className, data, renderResult, renderError }: CaptureFlowProps) {
  const [lang, setLang] = useState<Lang>(browserLang);
  const [state, setState] = useState<CaptureState>(
    token ? { phase: "consent" } : { phase: "error", detail: "no_token" },
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
    });
    session.current = s;
    void s.start(noFlashRequested); // called inside the click: the overlay may ask for fullscreen
  };

  const { phase, detail, tips, agentQuestions, weakConnection } = state;
  return (
    <main className={className ? `customer ${className}` : "customer"} data-phase={phase} lang={lang} {...data}>
      <video
        ref={video}
        className={CAMERA_PHASES.has(phase) ? `selfview selfview-${phase === "challenge" ? "hidden" : "shown"}` : "selfview-off"}
        muted
        playsInline
        aria-hidden="true"
      />
      {phase === "consent" && <Consent lang={lang} onLang={setLang} onStart={start} />}
      {phase === "camera" && <Status lang={lang} text="camera.asking" />}
      {phase === "coaching" && <Coaching lang={lang} tips={tips} />}
      {(phase === "preflight" || phase === "ready") && (
        <Status lang={lang} text="preflight.checking" hint="preflight.hint" />
      )}
      {phase === "challenge" && <Status lang={lang} text="challenge.look" />}
      {(phase === "uploading" || phase === "waiting") && (
        <Status lang={lang} text="waiting.text" hint={agentQuestions ? "agent.questions" : undefined} />
      )}
      {weakConnection && WEAK_PHASES.has(phase) && (
        <p className="muted weak-connection" role="status" aria-live="polite">
          {t("upload.weak", lang)}
        </p>
      )}
      {phase === "result" &&
        (renderResult ? renderResult(state, lang) : <Result lang={lang} message={detail} agentQuestions={agentQuestions} />)}
      {phase === "error" && (renderError ? renderError(state, lang) : <ErrorStep lang={lang} detail={detail} />)}
    </main>
  );
}
