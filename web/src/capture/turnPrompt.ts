/**
 * The v1 turn prompt: text and an arrow on the light overlay, with a small mirrored self-view (top corner, <= 25%
 * of the width) raised above the overlay for the turn only. Y5 replaces this with the full prompt and progress ring;
 * CaptureSession takes any `TurnPromptFactory`, so the swap is one option.
 *
 * The client never judges the turn; the prompt ends after durationMs whatever happened.
 */
import { now } from "./clock";
import { sleep } from "./flash";

export type TurnDirection = "left" | "right";
/** What runChallenge calls for a turn step; resolves with painted/ended in ms since t0. */
export type ShowTurnPrompt = (dir: TurnDirection, durationMs: number) => Promise<{ painted: number; ended: number }>;

export interface TurnPromptContext {
  overlay: { t0: number; showPrompt(text: string | null): void };
  /** the camera's <video>, shown as the self-view during the turn */
  video: HTMLVideoElement;
  /** the prompt text for a direction (customer strings) */
  text: (dir: TurnDirection) => string;
}
export type TurnPromptFactory = (ctx: TurnPromptContext) => ShowTurnPrompt;

/** Above the light overlay (z-index 2147483000). */
const SELF_VIEW_Z = "2147483001";

/**
 * The self-view is mirrored, so the person's own left is the left side of the screen: a left arrow for "left".
 * The arrow sits on the side the person turns towards.
 */
export const arrowFor = (dir: TurnDirection): string => (dir === "left" ? "←" : "→");

export function promptLine(dir: TurnDirection, text: string): string {
  return dir === "left" ? `${arrowFor(dir)} ${text}` : `${text} ${arrowFor(dir)}`;
}

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

/** Raises the self-view above the overlay; returns a function that puts it back. */
export function raiseSelfView(video: HTMLVideoElement): () => void {
  const before = video.style.cssText;
  Object.assign(video.style, {
    position: "fixed", top: "8px", right: "8px", left: "auto", width: "25vw", maxWidth: "25%", height: "auto",
    zIndex: SELF_VIEW_Z, transform: "scaleX(-1)", borderRadius: "8px", visibility: "visible", opacity: "1",
  });
  return () => {
    video.style.cssText = before;
  };
}

export const textTurnPrompt: TurnPromptFactory = ({ overlay, video, text }) => async (dir, durationMs) => {
  const lower = raiseSelfView(video);
  overlay.showPrompt(promptLine(dir, text(dir)));
  await nextFrame();
  await nextFrame();
  const painted = now() - overlay.t0;
  try {
    await sleep(durationMs);
  } finally {
    overlay.showPrompt(null);
    lower();
  }
  await nextFrame();
  await nextFrame();
  return { painted, ended: now() - overlay.t0 };
};
