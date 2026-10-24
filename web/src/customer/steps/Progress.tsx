import type { CustomerPhase } from "../../capture/session";
import { t, type Lang, type StringKey } from "../strings";

const STEPS: StringKey[] = ["progress.ready", "progress.camera", "progress.done"];

/** Which of the 3 steps a phase belongs to (0-based); null hides the indicator (challenge, error). */
export function stepOf(phase: CustomerPhase): number | null {
  switch (phase) {
    case "consent":
      return 0;
    case "camera":
    case "preflight":
    case "coaching":
    case "ready":
      return 1;
    case "uploading":
    case "waiting":
    case "result":
      return 2;
    default:
      return null;
  }
}

/**
 * The 3-step progress line: Get ready, Camera check, Done. The current step carries aria-current="step"; `complete`
 * ticks the current step too (the result is in).
 */
export function Progress({ lang, step, complete = false }: { lang: Lang; step: number; complete?: boolean }) {
  return (
    <ol className="kyc-steps" aria-label={t("progress.label", lang)}>
      {STEPS.map((key, i) => {
        const state = i < step || (complete && i === step) ? "done" : i === step ? "current" : "todo";
        return (
          <li key={key} className={`kyc-step is-${state}`} aria-current={i === step ? "step" : undefined}>
            <span className="kyc-dot" aria-hidden="true">
              {state === "done" ? (
                <svg viewBox="0 0 16 16" width="14" height="14">
                  <path d="m3.5 8.5 3 3 6-6.5" fill="none" stroke="currentColor" strokeWidth="2.2"
                    strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                i + 1
              )}
            </span>
            <span className="kyc-step-name">{t(key, lang)}</span>
          </li>
        );
      })}
    </ol>
  );
}
