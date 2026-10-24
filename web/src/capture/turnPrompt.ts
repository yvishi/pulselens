/**
 * The v1 turn prompt: text and an arrow on the light overlay, with a small mirrored self-view (top corner, <= 25%
 * of the width) raised above the overlay for the turn only. The customer flow uses the Y5 prompt with the progress
 * ring (customer/steps/TurnPrompt.tsx), which falls back to this one when the face tracker cannot load.
 *
 * The client never judges the turn; the prompt ends after durationMs whatever happened.
 */
import { now } from "./clock";
import type { FaceTracker } from "./face";
import { nextFrame, sleep } from "./util";

export type TurnDirection = "left" | "right";
/** What runChallenge calls for a turn step; resolves with painted/ended in ms since t0. */
export type ShowTurnPrompt = (dir: TurnDirection, durationMs: number) => Promise<{ painted: number; ended: number }>;

export interface TurnPromptContext {
  overlay: { t0: number; showPrompt(text: string | null): void };
  /** the camera's <video>, shown as the self-view during the turn */
  video: HTMLVideoElement;
  /** the prompt text for a direction (customer strings) */
  text: (dir: TurnDirection) => string;
  /** the session's shared face tracker (null when it cannot load); prompts that need one take it from here */
  faceTracker?: () => Promise<FaceTracker | null>;
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

/**
 * The skeleton every turn prompt shares: raise the self-view, show() the prompt, wait two frames (painted), hold for
 * durationMs, hide it (show's return) and put the self-view back, wait two frames (ended). Times are ms since t0.
 */
export async function runPrompt(
  ctx: Pick<TurnPromptContext, "overlay" | "video">,
  durationMs: number,
  show: () => () => void,
): Promise<{ painted: number; ended: number }> {
  const { overlay, video } = ctx;
  const lower = raiseSelfView(video);
  let hide: (() => void) | undefined;
  let painted: number;
  try {
    hide = show();
    await nextFrame();
    await nextFrame();
    painted = now() - overlay.t0;
    await sleep(durationMs);
  } finally {
    hide?.();
    lower();
  }
  await nextFrame();
  await nextFrame();
  return { painted, ended: now() - overlay.t0 };
}

export const textTurnPrompt: TurnPromptFactory = (ctx) => (dir, durationMs) =>
  runPrompt(ctx, durationMs, () => {
    ctx.overlay.showPrompt(promptLine(dir, ctx.text(dir)));
    return () => ctx.overlay.showPrompt(null);
  });
