import { describe, expect, it } from "vitest";
import { TURN_BASELINE_MS, TURN_FULL_DEG, TurnMeter, arrowSide, turnProgress } from "./turn";

describe("turnProgress", () => {
  it("progress is 0 at yaw 0, 1 at 20 deg in the requested direction, 0 in the wrong direction", () => {
    expect(TURN_FULL_DEG).toBe(20);
    // CONTRACT §1: positive yaw = the person's own left
    expect(turnProgress(0, 0, "left")).toBe(0);
    expect(turnProgress(20, 0, "left")).toBe(1);
    expect(turnProgress(10, 0, "left")).toBeCloseTo(0.5);
    expect(turnProgress(-20, 0, "left")).toBe(0);
    expect(turnProgress(0, 0, "right")).toBe(0);
    expect(turnProgress(-20, 0, "right")).toBe(1);
    expect(turnProgress(20, 0, "right")).toBe(0);
  });

  it("is relative to the resting yaw and clamped to 0..1", () => {
    expect(turnProgress(25, 5, "left")).toBe(1);
    expect(turnProgress(15, 5, "left")).toBeCloseTo(0.5);
    expect(turnProgress(60, 0, "left")).toBe(1);
    expect(turnProgress(-5, -5, "right")).toBe(0);
  });
});

describe("arrowSide", () => {
  it("arrow side matches mirrored view", () => {
    // mirrored front-camera self-view: the person's own left is the left of the screen
    expect(arrowSide("left", true)).toBe("left");
    expect(arrowSide("right", true)).toBe("right");
    // an unmirrored view shows their left on the right of the screen
    expect(arrowSide("left", false)).toBe("right");
    expect(arrowSide("right", false)).toBe("left");
  });
});

describe("TurnMeter", () => {
  it("takes the median yaw of the first 300 ms as rest, then reports progress", () => {
    const m = new TurnMeter("left");
    expect(TURN_BASELINE_MS).toBe(300);
    expect(m.update(2, 0)).toBe(0);
    expect(m.update(40, 100)).toBe(0); // an outlier in the baseline window
    expect(m.update(4, 200)).toBe(0);
    expect(m.update(14, 400)).toBeCloseTo(0.5); // rest = median(2, 40, 4) = 4
    expect(m.update(null, 450)).toBeCloseTo(0.5); // no face: keep the last value
    expect(m.update(-30, 500)).toBe(0);
  });

  it("stays 0 when no yaw arrives in the baseline window", () => {
    const m = new TurnMeter("right");
    expect(m.update(null, 0)).toBe(0);
    expect(m.update(null, 400)).toBe(0);
    expect(m.update(-5, 500)).toBe(0); // first yaw after the window becomes the rest
    expect(m.update(-15, 600)).toBeCloseTo(0.5);
  });
});
