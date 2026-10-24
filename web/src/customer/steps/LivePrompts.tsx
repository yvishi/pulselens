/**
 * The nod and digit prompts (config challenge.extra_prompts), drawn as the same dark card as the turn prompt, above the
 * light overlay. The nod raises the small mirrored self-view (as the turn does); a digit is just the number, large,
 * with "Say this number out loud".
 *
 * Guidance only: each prompt ends after durationMs whatever happened; the server judges the nod (head pitch) and the
 * lip timing. No audio is recorded, and the number said is not checked, only that the lips move when it appears.
 */
import type { ReactNode } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { runCard, type DigitPromptFactory, type NodPromptFactory } from "../../capture/livePrompts";
import { runPrompt } from "../../capture/turnPrompt";

/** Above the light overlay (2147483000) and the raised self-view (2147483001), like the turn prompt. */
const PROMPT_Z = "2147483002";

/** The turn prompt's card: white on dark navy, readable on any overlay colour; fits a 360 px screen. */
function Card({ children }: { children: ReactNode }) {
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
      {children}
    </div>
  );
}

export function NodPromptView({ text }: { text: string }) {
  return (
    <Card>
      <span aria-hidden="true" style={{ display: "flex", width: "clamp(40px, 12vw, 56px)", lineHeight: 0 }}>
        <svg viewBox="0 0 48 48" width="100%">
          <path d="M24 6v36M13 15l11-11 11 11M13 33l11 11 11-11" fill="none" stroke="#fff" strokeWidth="5"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <p style={{ margin: 0 }}>{text}</p>
    </Card>
  );
}

export function DigitView({ digit, text }: { digit: number; text: string }) {
  return (
    <Card>
      <p style={{ margin: 0 }}>{text}</p>
      <span data-digit={digit} style={{ font: "800 clamp(88px, 30vw, 132px)/1 var(--font-body, system-ui, sans-serif)" }}>
        {digit}
      </span>
    </Card>
  );
}

/** Mounts `view` in a full-screen, click-through host above the overlay; returns a function that removes it. */
function mount(view: ReactNode, tag: Record<string, string>): () => void {
  const host = document.createElement("div");
  Object.assign(host.dataset, tag);
  Object.assign(host.style, {
    position: "fixed", inset: "0", zIndex: PROMPT_Z, pointerEvents: "none", display: "flex",
    alignItems: "center", justifyContent: "center", padding: "16px", boxSizing: "border-box",
  });
  document.body.append(host);
  const root = createRoot(host);
  flushSync(() => root.render(view));
  return () => {
    root.unmount();
    host.remove();
  };
}

export const cardNodPrompt = (): NodPromptFactory => (ctx) => (durationMs) =>
  runPrompt(ctx, durationMs, () => mount(<NodPromptView text={ctx.nodText()} />, { nodPrompt: "" }));

export const cardDigitPrompt = (): DigitPromptFactory => (ctx) => (digit, durationMs) =>
  runCard(ctx.overlay, durationMs, () =>
    mount(<DigitView digit={digit} text={ctx.digitText()} />, { digitPrompt: String(digit) }));
