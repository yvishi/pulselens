import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { usePoll } from "./usePoll";

afterEach(() => cleanup());

function Probe({ fetch, done, onUnauthorized }: { fetch: () => Promise<number>; done?: (v: number) => boolean; onUnauthorized: () => void }) {
  const { value, error } = usePoll(fetch, 5, { done, onUnauthorized });
  return <p data-testid="out">{`${value ?? "-"}|${error ?? "-"}`}</p>;
}

const out = () => screen.getByTestId("out").textContent;

describe("usePoll", () => {
  it("polls until done, then stops", async () => {
    let n = 0;
    const fetch = vi.fn(async () => ++n);
    render(<Probe fetch={fetch} done={(v) => v >= 3} onUnauthorized={() => {}} />);
    await waitFor(() => expect(out()).toBe("3|-"));
    await new Promise((r) => setTimeout(r, 40));
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("stops and hands a 401 to onUnauthorized", async () => {
    const onUnauthorized = vi.fn();
    const fetch = vi.fn(async () => Promise.reject(new ApiError(401, "unauthorized")));
    render(<Probe fetch={fetch} onUnauthorized={onUnauthorized} />);
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 30));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("stops on a 404 with not_found", async () => {
    const fetch = vi.fn(async () => Promise.reject(new ApiError(404, "unknown_session")));
    render(<Probe fetch={fetch} onUnauthorized={() => {}} />);
    await waitFor(() => expect(out()).toBe("-|not_found"));
    await new Promise((r) => setTimeout(r, 30));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps trying while unreachable and clears the error once it answers", async () => {
    let calls = 0;
    const fetch = vi.fn(async () => (++calls < 3 ? Promise.reject(new TypeError("Failed to fetch")) : 7));
    render(<Probe fetch={fetch} done={() => true} onUnauthorized={() => {}} />);
    await waitFor(() => expect(out()).toBe("-|unreachable"));
    await waitFor(() => expect(out()).toBe("7|-"));
  });
});
