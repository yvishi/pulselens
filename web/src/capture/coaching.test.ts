import { describe, expect, it } from "vitest";
import { COACH_ROUNDS, coachTips, lumaInOut, summarise, type CoachMetrics, type CoachSample } from "./coaching";

/** A good picture: no tip fires. */
const good: CoachMetrics = {
  brightness: 120, faceLuma: 125, outsideLuma: 115, faceFraction: 0.12, faceBottom: 0.55, blur: 150, blurBaseline: 140,
};

describe("coachTips", () => {
  it("a good picture gets no tips", () => {
    expect(coachTips(good)).toEqual([]);
  });

  it("Face the light: brightness below 40", () => {
    expect(coachTips({ ...good, brightness: 30, faceLuma: 30, outsideLuma: 30 })).toEqual(["light"]);
    expect(coachTips({ ...good, brightness: 40 })).toEqual([]);
  });

  it("Too bright behind you: the luma outside the face far above the face's", () => {
    expect(coachTips({ ...good, faceLuma: 60, outsideLuma: 200 })).toEqual(["backlight"]);
    expect(coachTips({ ...good, faceLuma: 110, outsideLuma: 160 })).toEqual([]);
  });

  it("Move closer: face fraction below 0.02 (no face counts)", () => {
    expect(coachTips({ ...good, faceFraction: 0.01 })).toEqual(["closer"]);
    expect(coachTips({ ...good, faceFraction: 0, faceLuma: null, faceBottom: null })).toEqual(["closer"]);
    expect(coachTips({ ...good, faceFraction: null, faceLuma: null, faceBottom: null })).toEqual([]); // no detector
  });

  it("Show your shoulders: the face box bottom below 75% of the frame height", () => {
    expect(coachTips({ ...good, faceBottom: 0.8 })).toEqual(["shoulders"]);
    expect(coachTips({ ...good, faceBottom: 0.75 })).toEqual([]);
  });

  it("Hold still: blur below half the median of the first second", () => {
    expect(coachTips({ ...good, blur: 60, blurBaseline: 140 })).toEqual(["still"]);
    expect(coachTips({ ...good, blur: 80, blurBaseline: 140 })).toEqual([]);
    expect(coachTips({ ...good, blur: 1, blurBaseline: null })).toEqual([]);
  });

  it("shows at most 2 tips, most important first", () => {
    const bad: CoachMetrics = {
      brightness: 20, faceLuma: 20, outsideLuma: 20, faceFraction: 0.01, faceBottom: 0.9, blur: 1, blurBaseline: 100,
    };
    expect(coachTips(bad)).toEqual(["light", "closer"]);
  });

  it("runs up to 3 rounds", () => {
    expect(COACH_ROUNDS).toBe(3);
  });
});

describe("coaching measurements", () => {
  it("lumaInOut splits the mean luma inside and outside a face box", () => {
    const w = 10;
    const h = 10;
    const d = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const v = x < 5 ? 50 : 200;
        d.set([v, v, v, 255], (y * w + x) * 4);
      }
    }
    const r = lumaInOut(d, w, h, [0, 0, 0.5, 1]);
    expect(r.inside).toBeCloseTo(50, 5);
    expect(r.outside).toBeCloseTo(200, 5);
  });

  it("lumaInOut uses the same Rec.709 luma as quality.ts", () => {
    const w = 4;
    const h = 4;
    const d = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) d.set(x < 2 ? [255, 0, 0, 255] : [0, 0, 255, 255], (y * w + x) * 4);
    const r = lumaInOut(d, w, h, [0, 0, 0.5, 1]);
    expect(r.inside).toBeCloseTo(0.2126 * 255, 5);
    expect(r.outside).toBeCloseTo(0.0722 * 255, 5);
  });

  it("summarise takes medians; the blur baseline comes from samples in the first second", () => {
    const s = (t: number, blur: number, face: CoachSample["face"]): CoachSample => ({
      t, brightness: 100, blur, face, faceLuma: face ? 110 : null, outsideLuma: 90,
    });
    const samples = [
      s(0, 100, [0.4, 0.2, 0.2, 0.3]), s(400, 120, [0.4, 0.2, 0.2, 0.3]), s(800, 110, null),
      s(1200, 10, [0.4, 0.2, 0.2, 0.3]), s(1600, 12, undefined),
    ];
    const m = summarise(samples, 0);
    expect(m.blurBaseline).toBe(110);
    expect(m.blur).toBe(100);
    expect(m.brightness).toBe(100);
    expect(m.faceFraction).toBeCloseTo(0.06, 5); // median over the 4 samples where detection ran
    expect(m.faceBottom).toBeCloseTo(0.5, 5);
    expect(summarise([s(0, 5, undefined)], 0).faceFraction).toBeNull();
  });
});
