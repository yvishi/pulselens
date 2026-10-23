import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export type PollError = "not_found" | "unreachable";

export const POLL_ERROR_TEXT = {
  not_found: "Unknown session.",
  unreachable: "The PulseLens server is unreachable. Retrying…",
} as const;

interface Options<T> {
  /** stop polling once this is true for a value */
  done?: (value: T) => boolean;
  /** a 401 stops polling and calls this (the console then asks for the passcode again) */
  onUnauthorized: () => void;
  /** changing it restarts polling, e.g. after an action that changes the data */
  key?: unknown;
}

/**
 * Calls `fetch` now and every `intervalMs` until `done(value)`. A 404 stops with "not_found"; any other failure
 * shows "unreachable" and keeps trying. `fetch` and `done` are read on every tick, so they may change freely.
 */
export function usePoll<T>(fetch: () => Promise<T>, intervalMs: number, { done, onUnauthorized, key }: Options<T>) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<PollError | null>(null);
  const latest = useRef({ fetch, done, onUnauthorized });
  useEffect(() => {
    latest.current = { fetch, done, onUnauthorized };
  });

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      const { fetch: get, done: isDone, onUnauthorized: unauthorized } = latest.current;
      try {
        const v = await get();
        if (!alive) return;
        setValue(v);
        setError(null);
        if (isDone?.(v)) return;
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) return unauthorized();
        if (e instanceof ApiError && e.status === 404) return setError("not_found");
        setError("unreachable");
      }
      if (alive) timer = setTimeout(tick, intervalMs);
    };
    void tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [intervalMs, key]);

  return { value, error };
}
