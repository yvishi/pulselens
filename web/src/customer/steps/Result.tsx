import { useState } from "react";
import type { CustomerMessage } from "../../contracts";
import { resultKey, t, type Lang } from "../strings";
import { AgentArt, DoneArt, RetryArt } from "./Art";

const ART: Record<CustomerMessage, () => React.JSX.Element> = {
  continue: DoneArt,
  please_retry: RetryArt,
  please_wait: AgentArt,
  assisted_route: AgentArt,
};

/** The result, from CustomerStatus.message only: never a score, family, check or outcome. */
export function Result({
  lang, message, agentQuestions,
}: { lang: Lang; message: CustomerMessage; agentQuestions?: boolean }) {
  const [asked, setAsked] = useState(false);
  const Art = ART[message];
  return (
    <section className="step step-result" aria-live="polite">
      <Art />
      <p className="status-text result-text" role="status">
        {t(resultKey(message), lang)}
      </p>
      {agentQuestions && <p className="hint">{t("agent.questions", lang)}</p>}
      {message === "please_retry" &&
        (asked ? (
          <p className="callout">{t("result.please_retry.asked", lang)}</p>
        ) : (
          <div className="actions">
            <button type="button" className="btn btn-primary btn-big" onClick={() => setAsked(true)}>
              {t("result.please_retry.button", lang)}
            </button>
          </div>
        ))}
    </section>
  );
}
