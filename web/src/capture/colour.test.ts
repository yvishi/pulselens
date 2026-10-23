import { describe, expect, it } from "vitest";
import { isoluminantColour, neutralColour, relativeLuminance } from "./colour";

const HUES = [40, 80, 140, 200, 250, 300];

describe("isoluminantColour", () => {
  it.each(HUES)("hue %i keeps relative luminance within 5%% of 0.5", (hue) => {
    expect(Math.abs(relativeLuminance(isoluminantColour(hue)) - 0.5)).toBeLessThanOrEqual(0.025);
  });

  it("keeps every channel in 0..1", () => {
    for (const hue of [...HUES, 0, 90, 180, 270, 359.5]) {
      for (const c of isoluminantColour(hue)) {
        expect(c).toBeGreaterThanOrEqual(0);
        expect(c).toBeLessThanOrEqual(1);
      }
    }
  });

  it("gives distinct colours for distinct hues and honours Y", () => {
    expect(isoluminantColour(40)).not.toEqual(isoluminantColour(200));
    expect(relativeLuminance(isoluminantColour(140, 0.3))).toBeCloseTo(0.3, 2);
  });
});

describe("neutralColour", () => {
  it("is a grey at the same luminance", () => {
    const [r, g, b] = neutralColour();
    expect(r).toBe(g);
    expect(g).toBe(b);
    expect(relativeLuminance(neutralColour())).toBeCloseTo(0.5, 3);
  });
});
