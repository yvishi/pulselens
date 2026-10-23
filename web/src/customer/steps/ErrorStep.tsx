import type { CaptureErrorDetail } from "../../capture/session";
import { errorKey, t, type Lang } from "../strings";

const DETAILS: readonly string[] = [
  "insecure", "camera_denied", "camera_missing", "camera_busy", "camera_error", "expired", "failed", "no_token",
];

/** A plain message and no retry loop: the agent takes over. */
export function ErrorStep({ lang, detail }: { lang: Lang; detail: string | undefined }) {
  const d = (DETAILS.includes(detail ?? "") ? detail : "failed") as CaptureErrorDetail | "no_token";
  return (
    <section className="step" role="alert">
      <p className="status-text">{t(errorKey(d), lang)}</p>
    </section>
  );
}
