import { describe, expect, it } from "vitest";
import { boxOf, yawFromMatrix } from "./face";

describe("face helpers (no model needed)", () => {
  it("yaw is atan2(m[8], m[10]) of the column-major matrix, in degrees", () => {
    const a = (30 * Math.PI) / 180;
    const m = [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, -50, 1];
    expect(yawFromMatrix(m)).toBeCloseTo(30);
    expect(yawFromMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])).toBeCloseTo(0);
  });

  it("boxOf gives a clipped normalised box", () => {
    const b = boxOf([{ x: 0.2, y: 0.3 }, { x: 0.6, y: 0.9 }, { x: 1.2, y: 0.5 }])!;
    [0.2, 0.3, 0.8, 0.6].forEach((v, k) => expect(b[k]).toBeCloseTo(v));
    expect(boxOf([])).toBeNull();
  });
});
