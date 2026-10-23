import { t, type Lang } from "../strings";

/** Notice and consent: Start, or the no-flash choice (both are user gestures that start the session). */
export function Consent({ lang, onStart }: { lang: Lang; onStart: (noFlashRequested: boolean) => void }) {
  return (
    <section className="step" aria-labelledby="consent-title">
      <h1 id="consent-title">{t("consent.title", lang)}</h1>
      <p>{t("consent.body", lang)}</p>
      <p>{t("consent.privacy", lang)}</p>
      <p className="muted">{t("consent.photosensitive", lang)}</p>
      <div className="actions">
        <button type="button" className="primary" onClick={() => onStart(false)}>
          {t("consent.start", lang)}
        </button>
        <button type="button" onClick={() => onStart(true)}>
          {t("consent.noFlash", lang)}
        </button>
      </div>
    </section>
  );
}
