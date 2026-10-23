import { t, type Lang } from "../strings";

const LANGS: Lang[] = ["en", "hi"];

/** Notice and consent: Start, or the no-flash choice (both are user gestures that start the session). */
export function Consent({
  lang, onLang, onStart,
}: { lang: Lang; onLang: (l: Lang) => void; onStart: (noFlashRequested: boolean) => void }) {
  return (
    <section className="step" aria-labelledby="consent-title">
      <div className="lang-toggle" role="group" aria-label={t("lang.label", lang)}>
        {LANGS.map((l) => (
          <button key={l} type="button" lang={l} aria-pressed={lang === l} onClick={() => onLang(l)}>
            {t(`lang.${l}`, lang)}
          </button>
        ))}
      </div>
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
