/**
 * Photosensitivity guard (WCAG 2.3.1): at least 334 ms between colour changes, so never more than 3 per second.
 * The server's schedule already respects this; the client enforces it as a second line of defence by delaying.
 */
import { now } from "./clock";
import { sleep } from "./util";

export const MIN_CHANGE_GAP_MS = 334;

export class FlashLimiter {
  private last = -Infinity;

  constructor(private readonly gapMs = MIN_CHANGE_GAP_MS) {}

  /** ms to wait before a change at time t is allowed. */
  waitMs(t: number): number {
    return Math.max(0, this.last + this.gapMs - t);
  }

  record(t: number): void {
    this.last = t;
  }

  /** Waits until a change is allowed, runs it, and records the time it reported (performance.now() ms). */
  async change<T>(apply: () => Promise<T>, appliedAt: (result: T) => number = () => now()): Promise<T> {
    // Re-check after waking: a timer may fire a hair early, and the gap is a hard floor.
    for (let w = this.waitMs(now()); w > 0; w = this.waitMs(now())) await sleep(w);
    const result = await apply();
    this.record(appliedAt(result));
    return result;
  }
}

export { sleep };
