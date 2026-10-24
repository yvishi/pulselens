/**
 * Head-turn guidance maths (pure). The ring is guidance only: the client never judges the turn; the server does.
 *
 * Yaw sign (CONTRACT §1): positive when the person turns to their own left.
 */
import type { TurnDirection } from "./turnPrompt";
import { median } from "./util";

/** The ring is full at this many degrees from rest in the requested direction. */
export const TURN_FULL_DEG = 20;
/** The resting yaw is the median over the first 300 ms of the prompt. */
export const TURN_BASELINE_MS = 300;

/** 0..1: how far the head has turned from rest (yaw0) in the person's own `direction`; 0 the wrong way. */
export function turnProgress(yawDeg: number, yaw0: number, direction: TurnDirection): number {
  const sign = direction === "left" ? 1 : -1;
  const p = ((yawDeg - yaw0) * sign) / TURN_FULL_DEG;
  return Math.min(1, Math.max(0, p));
}

/**
 * The side of the screen the arrow points to. A mirrored (front-camera) self-view shows the person's own left on
 * the left of the screen, so the arrow follows their direction; an unmirrored view swaps it.
 */
export function arrowSide(direction: TurnDirection, mirrored: boolean): TurnDirection {
  if (mirrored) return direction;
  return direction === "left" ? "right" : "left";
}

/** Feeds yaw samples (null when no face) and reports the ring's progress; rest = median of the first 300 ms. */
export class TurnMeter {
  private start: number | null = null;
  private readonly baseline: number[] = [];
  private yaw0: number | null = null;
  private last = 0;

  constructor(readonly direction: TurnDirection, readonly baselineMs = TURN_BASELINE_MS) {}

  update(yawDeg: number | null, tMs: number): number {
    if (this.start === null) this.start = tMs;
    if (yawDeg === null) return this.last;
    if (this.yaw0 === null) {
      if (tMs - this.start < this.baselineMs || !this.baseline.length) {
        this.baseline.push(yawDeg);
        if (tMs - this.start < this.baselineMs) return this.last;
      }
      this.yaw0 = median(this.baseline);
    }
    this.last = turnProgress(yawDeg, this.yaw0, this.direction);
    return this.last;
  }
}
