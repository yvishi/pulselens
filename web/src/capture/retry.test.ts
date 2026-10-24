import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Challenge, Plan, Preflight } from "../contracts";
import { RETRY_DELAYS_MS, withRetries, withRetry } from "./retry";
import type { CaptureApi } from "./session";

const noSleep = vi.fn(() => Promise.resolve());

/** A call that fails with the given errors in turn, then resolves with `value`. */
function flaky<T>(errors: unknown[], value: T) {
  let k = 0;
  return vi.fn(() => (k < errors.length ? Promise.reject(errors[k++]) : Promise.resolve(value)));
}

describe("withRetry", () => {
  it("retries a network error and a 5xx with the backoff delays, then returns the value", async () => {
    const sleep = vi.fn((_ms: number) => Promise.resolve());
    const call = flaky([new TypeError("Failed to fetch"), new ApiError(500, "proxy")], "ok");
    await expect(withRetry(call, { sleep })).resolves.toBe("ok");
    expect(call).toHaveBeenCalledTimes(3);
    expect(sleep.mock.calls.map((c) => c[0])).toEqual(RETRY_DELAYS_MS);
  });

  it("gives up after the last delay and throws the last error", async () => {
    const err = new TypeError("Failed to fetch");
    const call = flaky([err, err, err, err], "never");
    await expect(withRetry(call, { sleep: noSleep })).rejects.toBe(err);
    expect(call).toHaveBeenCalledTimes(RETRY_DELAYS_MS.length + 1);
  });

  it("never retries a 4xx", async () => {
    const call = flaky([new ApiError(422, "bad_preflight")], "never");
    await expect(withRetry(call, { sleep: noSleep })).rejects.toMatchObject({ status: 422 });
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("treats an 'already done' answer on a retry as success, but not on the first attempt", async () => {
    const done = (e: unknown) => e instanceof ApiError && e.status === 409;
    const retried = flaky([new TypeError("reset"), new ApiError(409, "already_complete")], undefined);
    await expect(withRetry(retried, { sleep: noSleep, alreadyDone: done })).resolves.toBeUndefined();
    const first = flaky([new ApiError(409, "already_complete")], undefined);
    await expect(withRetry(first, { sleep: noSleep, alreadyDone: done })).rejects.toMatchObject({ status: 409 });
  });
});

describe("withRetries(api)", () => {
  const plan = { mode: "CAPABLE" } as Plan;
  const challenge = { challenge_id: "c" } as unknown as Challenge;
  const api = (over: Partial<CaptureApi>): CaptureApi => ({
    postPreflight: vi.fn(() => Promise.resolve(plan)),
    getChallenge: vi.fn(() => Promise.resolve(challenge)),
    postFrames: vi.fn(() => Promise.resolve()),
    postEvents: vi.fn(() => Promise.resolve()),
    completeSession: vi.fn(() => Promise.resolve()),
    getStatus: vi.fn(() => Promise.resolve({ state: "done", message: "continue" } as never)),
    ...over,
  });

  it("retries the one-off calls on a dropped connection", async () => {
    const reset = () => new TypeError("ERR_CONNECTION_RESET");
    const base = api({
      postPreflight: flaky([reset()], plan),
      getChallenge: flaky([reset()], challenge),
      postEvents: flaky([reset()], undefined),
      completeSession: flaky([reset()], undefined),
    });
    const r = withRetries(base, noSleep);
    await expect(r.postPreflight("s", "t", {} as Preflight)).resolves.toBe(plan);
    await expect(r.getChallenge("s", "t")).resolves.toBe(challenge);
    await expect(r.postEvents("s", "t", [])).resolves.toBeUndefined();
    await expect(r.completeSession("s", "t")).resolves.toBeUndefined();
    for (const f of [base.postPreflight, base.getChallenge, base.postEvents, base.completeSession]) {
      expect(f).toHaveBeenCalledTimes(2);
    }
  });

  it("a repeated /complete answered 409 already_complete means the first one landed", async () => {
    const base = api({ completeSession: flaky([new TypeError("reset"), new ApiError(409, "already_complete")], undefined) });
    await expect(withRetries(base, noSleep).completeSession("s", "t")).resolves.toBeUndefined();
  });

  it("leaves postFrames (the uploader retries it) and getStatus (the poll retries it) alone", () => {
    const base = api({});
    const r = withRetries(base, noSleep);
    expect(r.postFrames).toBe(base.postFrames);
    expect(r.getStatus).toBe(base.getStatus);
  });
});
