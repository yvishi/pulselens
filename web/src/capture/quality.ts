// Picture quality on a small RGBA downscale: brightness (mean luma) and blur (variance of the Laplacian).

/** Analysis size for quality samples (CONTRACT §3 `Preflight.blur`). */
export const QUALITY_SIZE: [number, number] = [160, 120];

/** Rec.709 luma weights, the same as the server's (server/pulselens/analysis/quality.py `LUMA`). */
export const LUMA_WEIGHTS = [0.2126, 0.7152, 0.0722] as const;
const [WR, WG, WB] = LUMA_WEIGHTS;

/** Luma (0..255) of the RGBA pixel at byte offset k: Rec.709 weights on the sRGB values. */
export const luma = (d: Uint8ClampedArray, k: number): number => WR * d[k]! + WG * d[k + 1]! + WB * d[k + 2]!;

/** Mean luma (0..255) of RGBA pixels. */
export function meanLuma(d: Uint8ClampedArray, w: number, h: number): number {
  let sum = 0;
  for (let k = 0; k < w * h * 4; k += 4) sum += luma(d, k);
  return w * h ? sum / (w * h) : 0;
}

/** Variance of the 4-neighbour Laplacian of luma over the interior pixels; low means blurred. */
export function laplacianVariance(d: Uint8ClampedArray, w: number, h: number): number {
  let n = 0;
  let sum = 0;
  let sum2 = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const k = (y * w + x) * 4;
      const lap = luma(d, k - 4) + luma(d, k + 4) + luma(d, k - 4 * w) + luma(d, k + 4 * w) - 4 * luma(d, k);
      sum += lap;
      sum2 += lap * lap;
      n++;
    }
  }
  if (!n) return 0;
  const mean = sum / n;
  return Math.max(0, sum2 / n - mean * mean);
}

export function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
}

/** A sampler that draws the current video frame at QUALITY_SIZE and measures it; returns null without a 2D canvas. */
export function videoQualitySampler(video: HTMLVideoElement): () => { blur: number; brightness: number } | null {
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
  return () => {
    if (!ctx || !video.videoWidth) return null;
    ctx.drawImage(video, 0, 0, w, h);
    const d = ctx.getImageData(0, 0, w, h).data;
    return { blur: laplacianVariance(d, w, h), brightness: meanLuma(d, w, h) };
  };
}
