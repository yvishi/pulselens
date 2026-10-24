// Plain-language words for the agent console. Bank agents are not technical: every code the
// server sends (outcome, state, mode, product, label kind) gets a short everyday phrase here.
import type { Mode, Outcome, Product, SessionState } from "../contracts";

export type PlainTone = "ok" | "warn" | "stop";

export const OUTCOME_PLAIN: Record<Outcome, { title: string; tone: PlainTone; next: string }> = {
  PASS: { title: "No signs of a fake found", tone: "ok", next: "Nothing raised risk. You can continue the call and approve." },
  RETRY_STEP_UP: { title: "Try again", tone: "warn", next: "Ask the customer to try again with a new link." },
  HUMAN_REVIEW: {
    title: "Needs your review",
    tone: "stop",
    next: "Something did not look right. Check the customer closely before you decide.",
  },
};

export const STATE_PLAIN: Record<SessionState, string> = {
  created: "Link sent, waiting for customer",
  preflight: "Customer is getting ready",
  capturing: "Check in progress",
  analysing: "Analysing…",
  done: "Finished",
  expired: "Link expired",
};

export const MODE_PLAIN: Record<Mode, string> = {
  CAPABLE: "Full check",
  CONSTRAINED: "Simpler check",
  NO_FLASH: "No flashing light",
};

export const PRODUCT_PLAIN: Record<Product, string> = {
  savings_account: "Savings account",
  instant_loan: "Instant loan",
};

/** Lab recordings only: the label's kind as a short phrase ("genuine", "screen replay", ...). */
export const LABEL_KIND_PLAIN: Record<string, string> = {
  genuine: "genuine",
  replay_screen: "screen replay",
  virtual_camera: "virtual camera",
  live_swap: "live face swap",
  photo_animation: "animated photo",
};

export function labelKindPlain(kind: string): string {
  return LABEL_KIND_PLAIN[kind] ?? kind.replace(/_/g, " ");
}

/** Wall-clock ms now. Server times (created_at_ms) are wall clock, unlike capture times (performance.now()). */
export function wallNow(): number {
  return new Date().getTime();
}

/** "just now", "3 min ago", "2 h ago", "4 days ago". Future times read as "just now". */
export function timeAgo(ms: number, now: number = wallNow()): string {
  const s = Math.max(0, Math.round((now - ms) / 1000));
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? "1 day ago" : `${d} days ago`;
}
