import { describe, expect, it } from "vitest";
import { laplacianVariance, meanLuma, median } from "./quality";

const W = 160;
const H = 120;

function image(pixel: (x: number, y: number) => number): Uint8ClampedArray {
  const d = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const k = (y * W + x) * 4;
      d[k] = d[k + 1] = d[k + 2] = pixel(x, y);
      d[k + 3] = 255;
    }
  }
  return d;
}

describe("quality", () => {
  it("meanLuma of a uniform 128 image is 128", () => {
    expect(meanLuma(image(() => 128), W, H)).toBeCloseTo(128, 6);
  });

  it("laplacianVariance of a flat image is 0 and of a checkerboard is > 1000", () => {
    expect(laplacianVariance(image(() => 90), W, H)).toBeCloseTo(0, 6);
    expect(laplacianVariance(image((x, y) => ((x + y) % 2 ? 255 : 0)), W, H)).toBeGreaterThan(1000);
  });

  it("median handles odd, even and empty lists", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 3, 2])).toBe(2.5);
    expect(median([])).toBe(0);
  });
});
