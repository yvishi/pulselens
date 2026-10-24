import { useState } from "react";
import type { CustomerMessage } from "../../contracts";
import { resultKey, t, type Lang } from "../strings";

/** The result, from CustomerStatus.message only: never a score, family, check or outcome. */
export function Result({
  lang, message, agentQuestions,
}: { lang: Lang; message: CustomerMessage; agentQuestions?: boolean }) {
  const [asked, setAsked] = useState(false);
  return (
    <section className="step" aria-live="polite">
      <p className="status-text" role="status">
        {t(resultKey(message), lang)}
      </p>
      {agentQuestions && <p>{t("agent.questions", lang)}</p>}
      {message === "please_retry" &&
        (asked ? (
          <p>{t("result.please_retry.asked", lang)}</p>
        ) : (
          <div className="actions">
            <button type="button" className="primary" onClick={() => setAsked(true)}>
              {t("result.please_retry.button", lang)}
            </button>
          </div>
        ))}
    </section>
  );
}
