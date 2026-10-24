/**
 * Retries for the session's one-off calls (preflight, challenge, events, complete), so one dropped connection (a
 * proxy 500, a reset, a timeout) no longer ends the whole session. Frames have their own retries in the uploader and
 * the status poll retries itself, so those two pass through unchanged.
 *
 * What a repeat does on the server (CONTRACT section 2):
 * - preflight: replaces the plan until the challenge is issued, so a repeat is safe;
 * - challenge: single use. If the first response was lost the repeat gets 409 challenge_already_issued and the
 *   session cannot recover (the client never saw its challenge); the retry still helps when the request never landed;
 * - events: appended again; integrity and the checks read the first event per step, so a duplicate is harmless;
 * - complete: a repeat gets 409 already_complete, which on a retry means the first attempt landed.
 */
import { ApiError } from "../api/client";
import { sleep as realSleep } from "./flash";
import type { CaptureApi } from "./session";
import { retryable } from "./uploader";

export const RETRY_DELAYS_MS = [500, 1500];

export interface RetryOptions {
  sleep?: (ms: number) => Promise<void>;
  /** an error that, on a retry, means an earlier attempt already did the job */
  alreadyDone?: (e: unknown) => boolean;
}

/** Runs `call`, retrying network errors, 5xx and timeouts after each delay; never a 4xx. */
export async function withRetry<T>(call: () => Promise<T>, opts: RetryOptions = {}): Promise<T> {
  const sleep = opts.sleep ?? realSleep;
  for (let attempt = 0; ; attempt++) {
    try {
      return await call();
    } catch (e) {
      if (attempt > 0 && opts.alreadyDone?.(e)) return undefined as T;
      if (!retryable(e) || attempt >= RETRY_DELAYS_MS.length) throw e;
      console.warn(`retrying after ${RETRY_DELAYS_MS[attempt]} ms`, e);
      await sleep(RETRY_DELAYS_MS[attempt]!);
    }
  }
}

const alreadyComplete = (e: unknown) => e instanceof ApiError && e.status === 409 && e.detail === "already_complete";

/** The API with the one-off calls wrapped in withRetry. */
export function withRetries(api: CaptureApi, sleep?: (ms: number) => Promise<void>): CaptureApi {
  return {
    ...api,
    postPreflight: (id, token, body) => withRetry(() => api.postPreflight(id, token, body), { sleep }),
    getChallenge: (id, token) => withRetry(() => api.getChallenge(id, token), { sleep }),
    postEvents: (id, token, events) => withRetry(() => api.postEvents(id, token, events), { sleep }),
    completeSession: (id, token) =>
      withRetry(() => api.completeSession(id, token), { sleep, alreadyDone: alreadyComplete }),
  };
}
