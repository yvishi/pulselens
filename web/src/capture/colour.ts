/**
 * Equal-luminance ("isoluminant") colours for the light challenge.
 *
 * Colours sit on a circle around a neutral grey in linear sRGB, inside the plane of constant relative luminance,
 * so a step changes the colour of the light on the face, not its brightness: the screen doesn't visibly flicker
 * and the echo is a chromaticity shift. All colours here are sRGB (gamma-encoded) channels in 0..1.
 */

export type RGB = [number, number, number];

/** Rec. 709 / sRGB relative-luminance weights for linear RGB. */
const W: RGB = [0.2126, 0.7152, 0.0722];

/** 0.5 gives the widest isoluminant circle in linear sRGB, so colour steps are as strong as they can be. */
export const NEUTRAL_LUMINANCE = 0.5;

/** Share of the largest in-gamut radius used, leaving room for 8-bit rounding on screen. */
const SATURATION = 0.95;

export const srgbToLinear = (c: number): number => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
export const linearToSrgb = (c: number): number => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);

/** Relative luminance (0..1) of an sRGB 0..1 colour. */
export const relativeLuminance = (rgb: RGB): number => rgb.reduce((sum, c, k) => sum + W[k]! * srgbToLinear(c), 0);

const dot = (a: RGB, b: RGB) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const scale = (a: RGB, s: number): RGB => [a[0] * s, a[1] * s, a[2] * s];
const sub = (a: RGB, b: RGB): RGB => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const unit = (a: RGB) => scale(a, 1 / Math.sqrt(dot(a, a)));
const cross = (a: RGB, b: RGB): RGB => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

// Orthonormal basis of the constant-luminance plane (W·x = 0). Hue 0 points towards red.
const U = unit(sub([1, 0, 0], scale(W, dot(W, [1, 0, 0]) / dot(W, W))));
const V = unit(cross(W, U));

function direction(hueDeg: number): RGB {
  const h = (hueDeg * Math.PI) / 180;
  return [0, 1, 2].map((k) => Math.cos(h) * U[k]! + Math.sin(h) * V[k]!) as RGB;
}

/** Largest radius at which every hue stays inside [0, 1] in linear RGB around grey Y. */
const radiusCache = new Map<number, number>();
function radius(Y: number): number {
  let r = radiusCache.get(Y);
  if (r === undefined) {
    r = Infinity;
    for (let h = 0; h < 360; h += 0.5) {
      for (const d of direction(h)) {
        if (d > 1e-12) r = Math.min(r, (1 - Y) / d);
        else if (d < -1e-12) r = Math.min(r, Y / -d);
      }
    }
    r *= SATURATION;
    radiusCache.set(Y, r);
  }
  return r;
}

const toSrgb = (linear: RGB): RGB => linear.map((c) => linearToSrgb(Math.min(1, Math.max(0, c)))) as RGB;

/** sRGB 0..1 colour of the given hue with relative luminance Y. */
export function isoluminantColour(hueDeg: number, Y = NEUTRAL_LUMINANCE): RGB {
  const d = direction(hueDeg);
  const r = radius(Y);
  return toSrgb([Y + r * d[0], Y + r * d[1], Y + r * d[2]]);
}

/** Grey shown between steps, at the same luminance as the colours. */
export const neutralColour = (Y = NEUTRAL_LUMINANCE): RGB => toSrgb([Y, Y, Y]);

export const cssColour = (rgb: RGB): string => `rgb(${rgb.map((c) => Math.round(255 * c)).join(", ")})`;
