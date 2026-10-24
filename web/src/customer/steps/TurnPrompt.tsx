/**
 * The head-turn prompt (Y5): a big arrow, "Turn your head to your LEFT, then back to the centre", and a live progress
 * ring driven by FaceTracker.yawDeg (full at 20 deg from rest), above the light overlay, with the small mirrored
 * self-view raised in the top corner.
 *
 * The ring is guidance only: the prompt ends after durationMs whatever happened; the server judges the turn.
 * If the face tracker cannot load, this is the plain text prompt (textTurnPrompt), with no ring.
 * The tracker is the session's shared one (ctx.faceTracker), so the page loads MediaPipe once.
 */
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { now } from "../../capture/clock";
import { createFaceTracker, type FaceTracker } from "../../capture/face";
import { TurnMeter, arrowSide } from "../../capture/turn";
import { runPrompt, textTurnPrompt, type TurnDirection, type TurnPromptFactory } from "../../capture/turnPrompt";

/** Above the light overlay (2147483000) and the raised self-view (2147483001). */
const PROMPT_Z = "2147483002";
/** ~15 Hz: enough for a smooth ring without starving the frame grabber. */
export const DETECT_EVERY_MS = 66;

const R = 54;
const CIRCUMFERENCE = 2 * Math.PI * R;

export interface TurnPromptViewProps {
  direction: TurnDirection;
  text: string;
  /** 0..1, or null when there is no face tracker (no ring) */
  progress: number | null;
  mirrored?: boolean;
}

/**
 * White text on a dark navy backdrop, so it reads on any overlay colour (fixed colours on purpose: the overlay behind it
 * changes colour, so the page tokens do not apply); fits a 360 px screen. Type follows the page fonts (:root vars).
 */
export function TurnPromptView({ direction, text, progress, mirrored = true }: TurnPromptViewProps) {
  const side = arrowSide(direction, mirrored);
  const arrow = (
    <span data-arrow={side} aria-hidden="true" style={{ display: "flex", width: "clamp(56px, 18vw, 80px)", lineHeight: 0 }}>
      <svg viewBox="0 0 48 48" width="100%" style={{ transform: side === "left" ? "scaleX(-1)" : undefined }}>
        <path d="M8 24h30M26 11l13 13-13 13" fill="none" stroke="#fff" strokeWidth="5.5" strokeLinecap="round"
          strokeLinejoin="round" />
      </svg>
    </span>
  );
  return (
    <div
      role="status"
      aria-live="assertive"
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: "16px", boxSizing: "border-box",
        maxWidth: "min(88vw, 420px)", padding: "22px 18px", borderRadius: "20px", textAlign: "center",
        color: "#fff", background: "rgba(14, 20, 35, 0.62)", boxShadow: "0 8px 32px rgba(0, 0, 0, 0.25)",
        font: "700 clamp(19px, 5.2vw, 24px)/1.3 var(--font-body, system-ui, sans-serif)",
      }}
    >
      {progress === null ? (
        arrow
      ) : (
        <div style={{ position: "relative", width: "clamp(112px, 36vw, 160px)", aspectRatio: "1" }}>
          <svg
            viewBox="0 0 120 120"
            data-ring=""
            data-progress={progress.toFixed(3)}
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", transform: "rotate(-90deg)" }}
            aria-hidden="true"
          >
            <circle cx="60" cy="60" r={R} fill="none" stroke="rgba(255,255,255,0.28)" strokeWidth="9" />
            <circle
              cx="60" cy="60" r={R} fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - progress)}
            />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {arrow}
          </div>
        </div>
      )}
      <p style={{ margin: 0 }}>{text}</p>
    </div>
  );
}

export interface RingTurnPromptOptions {
  /** overrides the tracker; default: the session's shared one (ctx.faceTracker), else createFaceTracker */
  loadTracker?: () => Promise<FaceTracker | null>;
  /** the self-view is mirrored (front camera); default true */
  mirrored?: boolean;
}

export const ringTurnPrompt = (opts: RingTurnPromptOptions = {}): TurnPromptFactory => (ctx) => {
  const { video, text } = ctx;
  let tracker: FaceTracker | null = null;
  let failed = false;
  (opts.loadTracker ?? ctx.faceTracker ?? createFaceTracker)().then(
    (t) => (t ? (tracker = t) : (failed = true)),
    () => (failed = true),
  );
  let lastTs = 0;

  return async (dir, durationMs) => {
    if (failed) return textTurnPrompt(ctx)(dir, durationMs);
    return runPrompt(ctx, durationMs, () => {
      const host = document.createElement("div");
      host.dataset.turnPrompt = dir;
      Object.assign(host.style, {
        position: "fixed", inset: "0", zIndex: PROMPT_Z, pointerEvents: "none", display: "flex",
        alignItems: "center", justifyContent: "center", padding: "16px", boxSizing: "border-box",
      });
      document.body.append(host);
      const root = createRoot(host);
      const line = text(dir);
      const meter = new TurnMeter(dir);
      const render = (progress: number | null) =>
        flushSync(() => root.render(<TurnPromptView direction={dir} text={line} progress={progress} mirrored={opts.mirrored} />));

      let shown: number | null = tracker ? 0 : null;
      render(shown);
      let running = true;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const tick = () => {
        if (!running) return;
        if (tracker) {
          const ts = (lastTs = Math.max(lastTs + 1, now())); // MediaPipe VIDEO mode needs increasing timestamps
          const p = meter.update(tracker.detect(video, ts).yawDeg, ts);
          if (shown === null || Math.abs(p - shown) >= 0.01) render((shown = p));
        }
        timer = setTimeout(tick, DETECT_EVERY_MS);
      };
      tick();

      return () => {
        running = false;
        clearTimeout(timer);
        root.unmount();
        host.remove();
      };
    });
  };
};
