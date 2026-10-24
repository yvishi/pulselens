/**
 * Small helpers shared across capture (framework-free). Times are performance.now() ms (CONTRACT section 1).
 */
import type { Preflight } from "../contracts";

/** Where a frame's time came from (CONTRACT section 1: captureTime ?? expectedDisplayTime ?? callback now). */
export type FrameClock = Preflight["clock"];

/** A frame's time from requestVideoFrameCallback metadata, falling back to the callback's own time. */
export function frameTime(
  md: { captureTime?: number; expectedDisplayTime?: number }, cbNow: number,
): { t: number; clock: FrameClock } {
  if (md.captureTime !== undefined) return { t: md.captureTime, clock: "captureTime" };
  if (md.expectedDisplayTime !== undefined) return { t: md.expectedDisplayTime, clock: "expectedDisplayTime" };
  return { t: cbNow, clock: "now" };
}

/** The median (mean of the middle two for an even count); 0 for an empty list. Does not mutate xs. */
export function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
}

/** Resolves after ms (a negative delay resolves on the next timer tick). */
export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, Math.max(0, ms)));

/** Resolves on the next animation frame. */
export const nextFrame = (): Promise<void> => new Promise<void>((r) => requestAnimationFrame(() => r()));
