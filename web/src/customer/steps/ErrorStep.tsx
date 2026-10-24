import type { CaptureErrorDetail } from "../../capture/session";
import { errorKey, t, type Lang } from "../strings";
import { PauseArt } from "./Art";

/** A plain message and no retry loop: the agent takes over. */
export function ErrorStep({ lang, error }: { lang: Lang; error: CaptureErrorDetail | "no_token" }) {
  return (
    <section className="step step-result step-error" role="alert">
      <PauseArt />
      <h1 className="result-title">{t("error.title", lang)}</h1>
      <p className="status-text">{t(errorKey(error), lang)}</p>
      <p className="hint">{t("error.next", lang)}</p>
    </section>
  );
}
