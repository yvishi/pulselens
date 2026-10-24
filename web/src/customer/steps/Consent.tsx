import { t, type Lang, type StringKey } from "../strings";
import { ClockIcon, ColoursIcon, ShieldIcon, TurnIcon } from "./Art";

const LANGS: Lang[] = ["en", "hi"];

/** EN / हिंदी as a two-segment switch; each segment is written in its own language. */
export function LangToggle({ lang, onLang }: { lang: Lang; onLang: (l: Lang) => void }) {
  return (
    <div className="lang-toggle" role="group" aria-label={t("lang.label", lang)}>
      {LANGS.map((l) => (
        <button key={l} type="button" lang={l} aria-pressed={lang === l} onClick={() => onLang(l)}>
          {t(`lang.${l}`, lang)}
        </button>
      ))}
    </div>
  );
}

const ITEMS: { key: StringKey; icon: () => React.JSX.Element }[] = [
  { key: "consent.item.colours", icon: ColoursIcon },
  { key: "consent.item.turn", icon: TurnIcon },
  { key: "consent.item.time", icon: ClockIcon },
];

/** Notice and consent: Start, or the no-flash choice (both are user gestures that start the session). */
export function Consent({ lang, onStart }: { lang: Lang; onStart: (noFlashRequested: boolean) => void }) {
  return (
    <section className="step step-consent" aria-labelledby="consent-title">
      <h1 id="consent-title">{t("consent.title", lang)}</h1>
      <p className="lead">{t("consent.lead", lang)}</p>
      <ul className="what-list">
        {ITEMS.map(({ key, icon: Icon }) => (
          <li key={key}>
            <span className="what-icon">
              <Icon />
            </span>
            <span>{t(key, lang)}</span>
          </li>
        ))}
      </ul>
      <p className="privacy">
        <ShieldIcon />
        <span>{t("consent.privacy", lang)}</span>
      </p>
      <div className="actions">
        <button type="button" className="btn btn-primary btn-big" onClick={() => onStart(false)}>
          {t("consent.start", lang)}
        </button>
        <p className="note">{t("consent.photosensitive", lang)}</p>
        <button type="button" className="btn" onClick={() => onStart(true)}>
          {t("consent.noFlash", lang)}
        </button>
      </div>
    </section>
  );
}
