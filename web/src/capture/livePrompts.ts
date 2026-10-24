/**
 * The two live prompts after the head turn (config challenge.extra_prompts): "Nod your head" and random digits to read
 * aloud, one at a time. A replayed or pre-recorded video cannot know when they come.
 *
 * Like the turn, the client never judges them: each prompt ends after durationMs whatever happened, and reports when it
 * reached the screen (painted, two frames after it was shown) and when it was taken down (ended), in ms since t0.
 * No audio is recorded: the server only times the lips against the digits; it does not know which number was said.
 *
 * These are the plain text versions on the light overlay (fallback and tests); the customer flow passes the card
 * prompts (customer/steps/LivePrompts.tsx).
 */
import { now } from "./clock";
import { runPrompt, type TurnPromptContext } from "./turnPrompt";
import { nextFrame, sleep } from "./util";

/** What runChallenge calls for a nod step; resolves with painted/ended in ms since t0. */
export type ShowNodPrompt = (durationMs: number) => Promise<{ painted: number; ended: number }>;
/** What runChallenge calls for a digit step; resolves with painted/ended in ms since t0. */
export type ShowDigitPrompt = (digit: number, durationMs: number) => Promise<{ painted: number; ended: number }>;

export interface LivePromptContext extends Pick<TurnPromptContext, "overlay" | "video"> {
  /** "Nod your head: down, then back up" (customer strings) */
  nodText: () => string;
  /** "Say this number out loud" (customer strings) */
  digitText: () => string;
}
export type NodPromptFactory = (ctx: LivePromptContext) => ShowNodPrompt;
export type DigitPromptFactory = (ctx: LivePromptContext) => ShowDigitPrompt;

export const DEFAULT_NOD_TEXT = "Nod your head: down, then back up";
export const DEFAULT_DIGIT_TEXT = "Say this number out loud";

/**
 * Like runPrompt, without raising the self-view (a digit flashes up three times; the corner video would flicker):
 * show(), two frames (painted), hold durationMs, hide, two frames (ended). Times are ms since overlay.t0.
 */
export async function runCard(
  overlay: { t0: number },
  durationMs: number,
  show: () => () => void,
): Promise<{ painted: number; ended: number }> {
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
  }
  await nextFrame();
  await nextFrame();
  return { painted, ended: now() - overlay.t0 };
}

/** The nod as text on the overlay, with the mirrored self-view raised (as for the turn). */
export const textNodPrompt: NodPromptFactory = (ctx) => (durationMs) =>
  runPrompt(ctx, durationMs, () => {
    ctx.overlay.showPrompt(`↕ ${ctx.nodText()}`);
    return () => ctx.overlay.showPrompt(null);
  });

/** A digit as text on the overlay. */
export const textDigitPrompt: DigitPromptFactory = (ctx) => (digit, durationMs) =>
  runCard(ctx.overlay, durationMs, () => {
    ctx.overlay.showPrompt(`${ctx.digitText()}: ${digit}`);
    return () => ctx.overlay.showPrompt(null);
  });
