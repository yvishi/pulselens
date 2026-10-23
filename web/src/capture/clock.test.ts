import { describe, expect, it } from "vitest";
import { now } from "./clock";

describe("clock", () => {
  it("is monotonic, in the performance.now() domain", () => {
    const a = now();
    const b = now();
    expect(b).toBeGreaterThanOrEqual(a);
    expect(Math.abs(a - performance.now())).toBeLessThan(1000);
  });
});
