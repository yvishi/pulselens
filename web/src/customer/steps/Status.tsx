import { t, type Lang, type StringKey } from "../strings";

/** A one-message screen: camera permission, preflight, challenge backdrop, uploading and waiting. */
export function Status({ lang, text, hint }: { lang: Lang; text: StringKey; hint?: StringKey }) {
  return (
    <section className="step" aria-live="polite">
      <p className="status-text" role="status">
        {t(text, lang)}
      </p>
      {hint && <p className="muted">{t(hint, lang)}</p>}
    </section>
  );
}
