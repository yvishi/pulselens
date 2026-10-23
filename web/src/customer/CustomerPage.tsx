// The customer flow at /customer/:sessionId?t=<token>. CaptureSession drives everything; this only renders its state.
import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CaptureSession, type CaptureState } from "../capture/session";
import "./customer.css";
import { Consent } from "./steps/Consent";
import { ErrorStep } from "./steps/ErrorStep";
import { Result } from "./steps/Result";
import { Status } from "./steps/Status";
import { t, turnKey, type Lang } from "./strings";

/** Phases where the camera is open and the <video> must stay rendered (the grabber reads it). */
const CAMERA_PHASES = new Set(["camera", "preflight", "coaching", "ready", "challenge"]);

export function CustomerPage() {
  const { sessionId = "" } = useParams();
  const [search] = useSearchParams();
  const token = search.get("t") ?? "";
  const lang: Lang = "en";
  const [state, setState] = useState<CaptureState>(
    token ? { phase: "consent" } : { phase: "error", detail: "no_token" },
  );
  const video = useRef<HTMLVideoElement>(null);
  const session = useRef<CaptureSession | null>(null);

  useEffect(() => () => session.current?.dispose(), []);

  const start = (noFlashRequested: boolean) => {
    if (session.current || !video.current) return;
    const s = new CaptureSession({
      sessionId, token, video: video.current, overlayRoot: document.body, onState: setState,
      turnText: (dir) => t(turnKey(dir), lang),
    });
    session.current = s;
    void s.start(noFlashRequested); // called inside the click: the overlay may ask for fullscreen
  };

  const { phase, detail } = state;
  return (
    <main className="customer" data-phase={phase}>
      <video
        ref={video}
        className={CAMERA_PHASES.has(phase) ? `selfview selfview-${phase === "challenge" ? "hidden" : "shown"}` : "selfview-off"}
        muted
        playsInline
        aria-hidden="true"
      />
      {phase === "consent" && <Consent lang={lang} onStart={start} />}
      {phase === "camera" && <Status lang={lang} text="camera.asking" />}
      {(phase === "preflight" || phase === "coaching" || phase === "ready") && (
        <Status lang={lang} text="preflight.checking" hint="preflight.hint" />
      )}
      {phase === "challenge" && <Status lang={lang} text="challenge.look" />}
      {(phase === "uploading" || phase === "waiting") && <Status lang={lang} text="waiting.text" />}
      {phase === "result" && <Result lang={lang} message={detail} />}
      {phase === "error" && <ErrorStep lang={lang} detail={detail} />}
    </main>
  );
}
