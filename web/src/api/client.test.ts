import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createSession, frameUrl, getStatus, postFrames } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the customer token and returns the parsed body", async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ state: "created", message: "please_wait" })));
    vi.stubGlobal("fetch", fetch);
    expect(await getStatus("s1", "tok")).toEqual({ state: "created", message: "please_wait" });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/sessions/s1/status");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("throws ApiError with the server detail on a non-2xx response", async () => {
    const body = JSON.stringify({ detail: "challenge_already_issued" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 409 })));
    const err = await createSession({}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, detail: "challenge_already_issued" });
  });

  it("names each frame part f{idx} and refuses a JPEG count that does not match", async () => {
    const fetch = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    const meta = { batch_seq: 0, frames: [{ idx: 7, t_ms: 0, w: 8, h: 6 }] };
    await postFrames("s1", "tok", meta, [new Blob(["x"], { type: "image/jpeg" })]);
    const form = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1].body as FormData;
    expect(form.has("f7") && form.has("meta")).toBe(true);
    expect(() => postFrames("s1", "tok", meta, [])).toThrow(/one JPEG per frame/);
  });

  it("builds frame URLs", () => {
    expect(frameUrl("s1", 12)).toBe("/api/sessions/s1/frames/12.jpg");
  });
});
