// Every customer-facing string, keyed, so Y6 can add Hindi (`hi`) beside `en` without touching the screens.
// The customer never sees a score, family, check id or outcome: only these texts.
import type { CustomerMessage } from "../contracts";
import type { CaptureErrorDetail } from "../capture/session";
import type { TurnDirection } from "../capture/turnPrompt";

const en = {
  "consent.title": "Quick camera check",
  "consent.body": "Your screen will show a few soft colours and ask you to turn your head. This takes about 20 seconds.",
  "consent.privacy": "We use your camera only for this check. Keep your face in view, in good light.",
  "consent.photosensitive":
    "If changing colours on a screen bother you, choose the second button: you will only be asked to turn your head.",
  "consent.start": "Start",
  "consent.noFlash": "I'd rather not see flashing colours",
  "camera.asking": "Please allow camera access when your browser asks.",
  "preflight.checking": "Checking your camera…",
  "preflight.hint": "Hold the screen at eye level and keep your face in view.",
  "challenge.look": "Keep looking at the screen.",
  "turn.left": "Turn your head to your LEFT, then back to the centre",
  "turn.right": "Turn your head to your RIGHT, then back to the centre",
  "waiting.text": "Please wait…",
  "result.continue": "Thank you, you can continue the call.",
  "result.please_retry": "Let's try that once more.",
  "result.please_retry.button": "Ask the agent for a new link",
  "result.please_retry.asked": "Please tell the agent on the call that you need a new link.",
  "result.please_wait": "Please wait for the agent.",
  "result.assisted_route": "The agent will help you complete KYC.",
  "error.camera_denied": "We need your camera for video-KYC. You can also continue with the agent.",
  "error.camera_missing": "We could not find a camera on this device. You can also continue with the agent.",
  "error.camera_busy": "Another app is using your camera. Close it, or continue with the agent.",
  "error.camera_error": "We could not start your camera. You can also continue with the agent.",
  "error.insecure": "This page needs a secure (https) link to use the camera. Please ask the agent for a new link.",
  "error.expired": "This link has expired. Please ask the agent for a new link.",
  "error.failed": "Something went wrong. Please tell the agent; they will help you continue.",
  "error.no_token": "This link is incomplete. Please ask the agent for a new link.",
} as const;

export type StringKey = keyof typeof en;
export type Lang = "en";

export const strings: Record<Lang, Record<StringKey, string>> = { en };

export function t(key: StringKey, lang: Lang = "en"): string {
  return strings[lang][key];
}

/** The only result text a customer sees, from CustomerStatus.message. */
export const resultKey = (m: CustomerMessage): StringKey => `result.${m}`;

export const errorKey = (d: CaptureErrorDetail | "no_token"): StringKey => `error.${d}`;

export const turnKey = (dir: TurnDirection): StringKey => `turn.${dir}`;
