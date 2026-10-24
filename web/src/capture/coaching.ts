/**
 * Coaching: measure the picture in the browser and show at most 2 plain tips. Up to 3 rounds of 3 s, then the
 * session continues anyway: the server's planner decides the mode. Poor capture is never a fail here; later
 * checks abstain on it instead. Tips help the customer, they never score anyone.
 */
import { now } from "./clock";
import { createFaceTracker, type FaceTracker } from "./face";
import { QUALITY_SIZE, laplacianVariance, luma, meanLuma, median } from "./quality";

export type CoachTip = "light" | "backlight" | "closer" | "shoulders" | "still";

export interface CoachMetrics {
  /** mean luma (0..255) of the whole frame */
  brightness: number;
  /** mean luma inside the face box; null without a face */
  faceLuma: number | null;
  /** mean luma outside the face box; null without a face */
  outsideLuma: number | null;
  /** face box area / frame area; 0 = no face found; null = no face detector (face tips are skipped) */
  faceFraction: number | null;
  /** bottom of the face box as a fraction of the frame height; null without a face */
  faceBottom: number | null;
  /** variance of the Laplacian (low = blurred) */
  blur: number;
  /** median blur over the first 1 s of coaching; null before it is known */
  blurBaseline: number | null;
}

/** Tip limits. Lenient starting points: tune from genuine set A sessions if tips fire on good pictures. */
export const COACH_LIMITS = {
  /** frame darker than this -> face the light */
  minBrightness: 40,
  /** outside the face this many times brighter than the face, and bright -> light behind you */
  backlightRatio: 2,
  minOutsideForBacklight: 100,
  /** face smaller than this share of the frame -> move closer */
  minFaceFraction: 0.02,
  /** face box bottom below this share of the frame height -> no room for the shoulders */
  maxFaceBottom: 0.75,
  /** blur below baseline * this -> hold still */
  stillRatio: 0.5,
  /** the blur baseline is the median of this first window */
  baselineMs: 1000,
} as const;

export const COACH_ROUNDS = 3;
export const COACH_ROUND_MS = 3000;
export const COACH_SAMPLE_MS = 200;
export const MAX_TIPS = 2;

/** At most 2 tips, most important first. */
export function coachTips(m: CoachMetrics): CoachTip[] {
  const L = COACH_LIMITS;
  const tips: CoachTip[] = [];
  if (m.brightness < L.minBrightness) tips.push("light");
  if (
    m.faceLuma !== null && m.outsideLuma !== null && m.outsideLuma >= L.minOutsideForBacklight &&
    m.outsideLuma > L.backlightRatio * m.faceLuma
  ) {
    tips.push("backlight");
  }
  if (m.faceFraction !== null && m.faceFraction < L.minFaceFraction) tips.push("closer");
  if (m.faceBottom !== null && m.faceBottom > L.maxFaceBottom) tips.push("shoulders");
  if (m.blurBaseline !== null && m.blur < m.blurBaseline * L.stillRatio) tips.push("still");
  return tips.slice(0, MAX_TIPS);
}

type Box = [number, number, number, number];

/** Mean luma inside and outside a face box given as [x, y, w, h] fractions of the frame. */
export function lumaInOut(d: Uint8ClampedArray, w: number, h: number, box: Box): { inside: number; outside: number } {
  const x0 = Math.max(0, Math.floor(box[0] * w));
  const y0 = Math.max(0, Math.floor(box[1] * h));
  const x1 = Math.min(w, Math.ceil((box[0] + box[2]) * w));
  const y1 = Math.min(h, Math.ceil((box[1] + box[3]) * h));
  let inSum = 0;
  let inN = 0;
  let total = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const k = (y * w + x) * 4;
      const v = luma(d, k);
      total += v;
      if (x >= x0 && x < x1 && y >= y0 && y < y1) {
        inSum += v;
        inN++;
      }
    }
  }
  const outN = w * h - inN;
  return { inside: inN ? inSum / inN : 0, outside: outN ? (total - inSum) / outN : 0 };
}

export interface CoachSample {
  /** performance.now() ms */
  t: number;
  brightness: number;
  blur: number;
  /** face box; null = no face found; undefined = no detector yet */
  face: Box | null | undefined;
  faceLuma: number | null;
  outsideLuma: number | null;
}

/** One round's metrics: medians of its samples. The blur baseline is the median of samples before start + 1 s. */
export function summarise(samples: CoachSample[], startMs: number, baseline?: number | null): CoachMetrics {
  const early = samples.filter((s) => s.t < startMs + COACH_LIMITS.baselineMs).map((s) => s.blur);
  const ran = samples.filter((s) => s.face !== undefined);
  const faces = samples.filter((s): s is CoachSample & { face: Box } => !!s.face);
  return {
    brightness: median(samples.map((s) => s.brightness)),
    faceLuma: faces.length ? median(faces.map((s) => s.faceLuma ?? 0)) : null,
    outsideLuma: faces.length ? median(faces.map((s) => s.outsideLuma ?? 0)) : null,
    faceFraction: ran.length ? median(ran.map((s) => (s.face ? s.face[2] * s.face[3] : 0))) : null,
    faceBottom: faces.length ? median(faces.map((s) => s.face[1] + s.face[3])) : null,
    blur: median(samples.map((s) => s.blur)),
    blurBaseline: baseline !== undefined ? baseline : early.length ? median(early) : null,
  };
}

/** Measures the picture for a window; keeps the first-second blur baseline across rounds. */
export interface CoachMeter {
  /** null when nothing could be sampled (no 2D canvas, no video yet): no tips then */
  measure(ms: number): Promise<CoachMetrics | null>;
}

/** The browser meter: samples about 5 frames per second at QUALITY_SIZE, with the face tracker once it loads. */
export function createCoachMeter(
  video: HTMLVideoElement,
  tracker: Promise<FaceTracker | null> = createFaceTracker().catch(() => null),
  clock: () => number = now,
): CoachMeter {
  const [w, h] = QUALITY_SIZE;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  let ctx: CanvasRenderingContext2D | null = null;
  try {
    ctx = canvas.getContext("2d", { willReadFrequently: true });
  } catch {
    ctx = null;
  }
  let face: FaceTracker | null | undefined;
  void tracker.then((t) => (face = t), () => (face = null));
  let baseline: number | null | undefined;
  let lastT = -1;

  const sample = (): CoachSample | null => {
    if (!ctx || !video.videoWidth) return null;
    ctx.drawImage(video, 0, 0, w, h);
    const d = ctx.getImageData(0, 0, w, h).data;
    const t = clock();
    let box: Box | null | undefined; // undefined while the detector loads, or without one: face tips are skipped
    if (face) {
      lastT = Math.max(t, lastT + 1); // MediaPipe VIDEO mode needs increasing timestamps
      box = face.detect(video, lastT).box;
    }
    const io = box ? lumaInOut(d, w, h, box) : null;
    return {
      t, brightness: meanLuma(d, w, h), blur: laplacianVariance(d, w, h), face: box,
      faceLuma: io?.inside ?? null, outsideLuma: io?.outside ?? null,
    };
  };

  return {
    async measure(ms) {
      const start = clock();
      const samples: CoachSample[] = [];
      while (clock() - start < ms) {
        const s = sample();
        if (s) samples.push(s);
        await new Promise((r) => setTimeout(r, COACH_SAMPLE_MS));
      }
      if (!samples.length) return null;
      const m = summarise(samples, start, baseline);
      if (baseline === undefined) baseline = m.blurBaseline;
      return m;
    },
  };
}
