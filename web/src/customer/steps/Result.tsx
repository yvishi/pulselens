import { useState } from "react";
import type { CustomerMessage } from "../../contracts";
import { resultKey, t, type Lang } from "../strings";

const MESSAGES: readonly CustomerMessage[] = ["continue", "please_retry", "please_wait", "assisted_route"];

/** The result, from CustomerStatus.message only: never a score, family, check or outcome. */
export function Result({ lang, message }: { lang: Lang; message: string | undefined }) {
  const [asked, setAsked] = useState(false);
  const m: CustomerMessage = MESSAGES.includes(message as CustomerMessage) ? (message as CustomerMessage) : "please_wait";
  return (
    <section className="step" aria-live="polite">
      <p className="status-text" role="status">
        {t(resultKey(m), lang)}
      </p>
      {m === "please_retry" &&
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
