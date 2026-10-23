/**
 * Runs a server Challenge on the device (CONTRACT section 3): neutral grey for baseline_ms, then each step at its
 * start_offset_ms after the baseline. A colour step paints, holds for dwell_ms and clears; a turn step hands over
 * to showTurnPrompt. Every colour change goes through a FlashLimiter (>= 334 ms apart, so <= 3 per second).
 */
import type { Challenge, ChallengeEvent, ColourStep } from "../contracts";
import { now } from "./clock";
import { isoluminantColour } from "./colour";
import { FlashLimiter, sleep } from "./flash";
import type { LightOverlay } from "./overlay";

/** What runChallenge needs from the overlay (LightOverlay, or a fake in tests). */
export type Overlay = Pick<LightOverlay, "t0" | "paint" | "clear">;

export interface ChallengeDeps {
  overlay: Overlay;
  /** performance.now() at the challenge start. */
  t0: number;
  /** Shows the turn prompt; resolves with painted/ended in ms since t0. */
  showTurnPrompt: (dir: "left" | "right", durationMs: number) => Promise<{ painted: number; ended: number }>;
  /** A reason to skip the next colour step ("fps_drop", "page_hidden", "no_flash") or null. */
  shouldSkipLight: () => string | null;
}

/** Saturated red ([345, 360) and [0, 15]) is never shown: photosensitivity. */
export const isRedHue = (hueDeg: number): boolean => {
  const h = ((hueDeg % 360) + 360) % 360;
  return h >= 345 || h <= 15;
};

const sleepUntil = (t: number) => sleep(t - now());

export async function runChallenge(ch: Challenge, deps: ChallengeDeps): Promise<ChallengeEvent[]> {
  const red = ch.steps.find((s): s is ColourStep => s.kind === "colour" && isRedHue(s.hue_deg));
  if (red) throw new Error(`refusing red hue ${red.hue_deg} in step ${red.step_id}`);

  const { overlay, t0 } = deps;
  overlay.t0 = t0;
  const limiter = new FlashLimiter();
  const change = (apply: () => Promise<number>) => limiter.change(apply, (t) => t + t0);
  const stepsStart = now() + ch.baseline_ms; // the overlay is already neutral grey for the baseline
  const events: ChallengeEvent[] = [];

  for (const step of [...ch.steps].sort((a, b) => a.start_offset_ms - b.start_offset_ms)) {
    await sleepUntil(stepsStart + step.start_offset_ms);
    if (step.kind === "turn") {
      const { painted, ended } = await deps.showTurnPrompt(step.direction, step.duration_ms);
      events.push({ step_id: step.step_id, status: "shown", painted_t_ms: painted, ended_t_ms: ended, shown_rgb: null,
        skip_reason: null });
      continue;
    }
    const reason = deps.shouldSkipLight();
    if (reason) {
      events.push({ step_id: step.step_id, status: "skipped", painted_t_ms: null, ended_t_ms: null, shown_rgb: null,
        skip_reason: reason });
      continue;
    }
    const rgb = isoluminantColour(step.hue_deg);
    const painted = await change(() => overlay.paint(rgb));
    await sleepUntil(t0 + painted + step.dwell_ms);
    const ended = await change(() => overlay.clear());
    events.push({ step_id: step.step_id, status: "shown", painted_t_ms: painted, ended_t_ms: ended, shown_rgb: rgb,
      skip_reason: null });
  }
  return events;
}
