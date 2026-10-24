import type { CaptureErrorDetail } from "../../capture/session";
import { errorKey, t, type Lang } from "../strings";

/** A plain message and no retry loop: the agent takes over. */
export function ErrorStep({ lang, error }: { lang: Lang; error: CaptureErrorDetail | "no_token" }) {
  return (
    <section className="step" role="alert">
      <p className="status-text">{t(errorKey(error), lang)}</p>
    </section>
  );
}
