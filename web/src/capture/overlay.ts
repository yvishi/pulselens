/**
 * The light overlay: a <div> above everything that shows the challenge colours.
 *
 * "fullscreen" covers the viewport (phones, and desktops once requestFullscreen() succeeds); "border" paints a
 * frame of 18% of the shorter side and leaves the middle see-through (desktop fallback). Between colours it shows
 * a grey at the colours' luminance, so a step changes hue, not brightness. paint() and clear() resolve after two
 * animation frames, i.e. once the change has reached the screen, with that time in ms since t0.
 */
import { now } from "./clock";
import { NEUTRAL_LUMINANCE, cssColour, neutralColour, type RGB } from "./colour";

export type OverlayMode = "fullscreen" | "border";

export const BORDER_FRAC = 0.18;

/** Phones always use the full-screen overlay; desktops only when the browser grants fullscreen. */
export async function chooseOverlayMode(desktop: boolean, el: Element = document.documentElement): Promise<OverlayMode> {
  if (!desktop) return "fullscreen";
  try {
    if (!document.fullscreenElement) await el.requestFullscreen();
    return "fullscreen";
  } catch {
    return "border";
  }
}

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

export class LightOverlay {
  readonly element: HTMLDivElement;
  readonly prompt: HTMLDivElement;
  /** performance.now() at the challenge start; paint() and clear() report times relative to it. */
  t0: number;
  private readonly neutral: RGB;
  private colour: RGB;

  constructor(
    root: HTMLElement,
    readonly mode: OverlayMode,
    opts: { t0?: number; Y?: number } = {},
  ) {
    this.t0 = opts.t0 ?? 0;
    this.neutral = neutralColour(opts.Y ?? NEUTRAL_LUMINANCE);
    this.colour = this.neutral;
    this.element = document.createElement("div");
    this.element.dataset.lightOverlay = mode;
    Object.assign(this.element.style, {
      position: "fixed", inset: "0", zIndex: "2147483000", pointerEvents: "none", boxSizing: "border-box",
      borderStyle: "solid", borderWidth: "0", display: "flex", alignItems: "center", justifyContent: "center",
    });
    // Readable on any colour: white text on a dark 50% backdrop.
    this.prompt = document.createElement("div");
    Object.assign(this.prompt.style, {
      display: "none", maxWidth: "80%", padding: "12px 20px", borderRadius: "12px", textAlign: "center",
      color: "#fff", background: "rgba(0, 0, 0, 0.5)", font: "600 22px system-ui, sans-serif",
    });
    this.element.append(this.prompt);
    root.append(this.element);
    addEventListener("resize", this.layout);
    this.layout();
  }

  private readonly layout = (): void => {
    const css = cssColour(this.colour);
    if (this.mode === "fullscreen") {
      this.element.style.background = css;
      return;
    }
    this.element.style.borderWidth = `${Math.round(BORDER_FRAC * Math.min(innerWidth, innerHeight))}px`;
    this.element.style.borderColor = css;
  };

  /** Shows a prompt over the colour (null hides it). */
  showPrompt(text: string | null): void {
    this.prompt.textContent = text ?? "";
    this.prompt.style.display = text ? "block" : "none";
  }

  private async show(rgb: RGB): Promise<number> {
    await nextFrame();
    this.colour = rgb;
    this.layout();
    await nextFrame();
    return now() - this.t0;
  }

  /** Sets the colour; resolves with painted_t_ms. */
  paint(rgb: RGB): Promise<number> {
    return this.show(rgb);
  }

  /** Back to neutral grey; resolves with ended_t_ms. */
  clear(): Promise<number> {
    return this.show(this.neutral);
  }

  dispose(): void {
    removeEventListener("resize", this.layout);
    this.element.remove();
    if (this.mode === "fullscreen" && document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
  }
}
