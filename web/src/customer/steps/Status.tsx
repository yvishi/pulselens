import type { ReactNode } from "react";
import { t, type Lang, type StringKey } from "../strings";

/** A one-message screen: camera permission, preflight, challenge backdrop, uploading and waiting. */
export function Status({ lang, text, hint, art }: { lang: Lang; text: StringKey; hint?: StringKey; art?: ReactNode }) {
  return (
    <section className="step step-status" aria-live="polite">
      {art && <div className="status-art">{art}</div>}
      <p className="status-text" role="status">
        {t(text, lang)}
      </p>
      {hint && <p className="hint">{t(hint, lang)}</p>}
    </section>
  );
}

/** Three soft dots that breathe in turn (still under prefers-reduced-motion). */
export function Waiting() {
  return (
    <span className="waiting-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}
