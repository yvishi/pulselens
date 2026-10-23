import type { CoachTip } from "../../capture/coaching";
import { coachKey, t, type Lang } from "../strings";

/** One coaching round: at most 2 plain tips. Never a score; the flow continues on its own after 3 rounds. */
export function Coaching({ lang, tips }: { lang: Lang; tips: CoachTip[] | undefined }) {
  return (
    <section className="step" aria-live="polite">
      <p className="status-text" role="status">
        {t("coaching.title", lang)}
      </p>
      <ul className="tips">
        {(tips ?? []).slice(0, 2).map((tip) => (
          <li key={tip}>{t(coachKey(tip), lang)}</li>
        ))}
      </ul>
      <p className="muted">{t("coaching.hint", lang)}</p>
    </section>
  );
}
