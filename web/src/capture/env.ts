// Browser, platform and sensor detection. The UA parsers are pure so they are unit-tested.
import type { Platform } from "../contracts";

const BROWSERS: [RegExp, string][] = [
  [/Edg(?:A|iOS)?\/(\d+)/, "Edge"],
  [/SamsungBrowser\/([\d.]+)/, "Samsung Internet"],
  [/OPR\/(\d+)/, "Opera"],
  [/CriOS\/(\d+)/, "Chrome iOS"],
  [/FxiOS\/(\d+)/, "Firefox iOS"],
  [/Firefox\/(\d+)/, "Firefox"],
  [/Chrome\/(\d+)/, "Chrome"],
  [/Version\/([\d.]+).*Safari/, "Safari"],
];

function parseOs(ua: string): string {
  let m: RegExpExecArray | null;
  if ((m = /Android (\d+(?:\.\d+)?)/.exec(ua))) return `Android ${m[1]}`;
  if ((m = /(?:iPhone|iPad|iPod).*? OS (\d+)_(\d+)/.exec(ua))) return `iOS ${m[1]}.${m[2]}`;
  if (/Windows NT/.test(ua)) return "Windows";
  if (/CrOS/.test(ua)) return "ChromeOS";
  if ((m = /Mac OS X (\d+)[._](\d+)/.exec(ua))) return `macOS ${m[1]}.${m[2]}`;
  if (/Linux/.test(ua)) return "Linux";
  return "unknown";
}

export function parseUserAgent(ua: string): { browser: string; os: string } {
  for (const [re, name] of BROWSERS) {
    const m = re.exec(ua);
    if (m) return { browser: `${name} ${m[1]}`, os: parseOs(ua) };
  }
  return { browser: "unknown", os: parseOs(ua) };
}

/** An iPad reports a Mac UA, so a Mac UA with a touch screen counts as iOS. */
export function platformOf(ua: string, maxTouchPoints: number): Platform {
  if (/Android/.test(ua)) return "android";
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouchPoints > 1)) return "ios";
  if (/Windows NT|Macintosh|CrOS|X11|Linux/.test(ua)) return "desktop";
  return "unknown";
}

/**
 * Whether a camera can be asked for an exact native mode (resizeMode "none"). Safari, every iOS browser (all WebKit)
 * and Firefox rescale any mode, so the unusual probe mode means nothing there.
 */
export function supportsResizeMode(
  ua = navigator.userAgent,
  supported: MediaTrackSupportedConstraints & { resizeMode?: boolean } = navigator.mediaDevices?.getSupportedConstraints?.() ?? {},
): boolean {
  if (/Firefox|FxiOS|iPhone|iPad|iPod/.test(ua) || parseUserAgent(ua).browser.startsWith("Safari")) return false;
  return !!supported.resizeMode;
}

/** True when a devicemotion event with a rotation rate arrives within `timeoutMs`. */
export function detectGyro(timeoutMs = 1000): Promise<boolean> {
  if (typeof DeviceMotionEvent === "undefined") return Promise.resolve(false);
  return new Promise((resolve) => {
    const done = (v: boolean) => {
      removeEventListener("devicemotion", onMotion);
      clearTimeout(timer);
      resolve(v);
    };
    const onMotion = (e: DeviceMotionEvent) => {
      const r = e.rotationRate;
      if (r && (r.alpha !== null || r.beta !== null || r.gamma !== null)) done(true);
    };
    const timer = setTimeout(() => done(false), timeoutMs);
    addEventListener("devicemotion", onMotion);
  });
}

/** Phones need HTTPS for the camera and motion sensors. */
export function secureContextError(): string | null {
  if (!globalThis.isSecureContext) return "This page must be opened over HTTPS (use the tunnel URL) to use the camera.";
  if (!navigator.mediaDevices?.getUserMedia) return "This browser does not give web pages access to the camera.";
  return null;
}
