import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { FrameBatchMeta } from "../contracts";
import type { GrabbedFrame } from "./grabber";
import { FrameUploader, MAX_BATCH, MAX_QUEUE, type PostFrames } from "./uploader";

const frame = (idx: number): GrabbedFrame => ({ idx, t_ms: idx * 33.3, w: 640, h: 480, jpeg: new Blob(["x"]) });

type Call = { meta: FrameBatchMeta; n: number };

/** A postFrames fake: logs each call; `reply` decides each call's fate (resolve, or throw an error). */
function fakePost(reply: (call: Call, k: number) => Promise<void> = () => Promise.resolve()) {
  const calls: Call[] = [];
  const post: PostFrames = vi.fn((_id: string, _token: string, meta: FrameBatchMeta, jpegs: Blob[]) => {
    const call = { meta: structuredClone(meta), n: jpegs.length };
    calls.push(call);
    return reply(call, calls.length - 1);
  });
  return { post, calls };
}

function uploader(post: PostFrames, extra: Partial<ConstructorParameters<typeof FrameUploader>[0]> = {}) {
  return new FrameUploader({ sessionId: "s", token: "tok", batchMs: 1000, postFrames: post, ...extra });
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("FrameUploader", () => {
  it("sends one batch per batchMs, at most 30 frames each, in idx order", async () => {
    const { post, calls } = fakePost();
    const up = uploader(post);
    for (let i = 0; i < 45; i++) up.push(frame(i));
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls).toHaveLength(1);
    expect(calls[0]!.meta.frames.map((f) => f.idx)).toEqual([...Array(30).keys()]);
    expect(calls[0]!.meta.batch_seq).toBe(0);
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls).toHaveLength(2);
    expect(calls[1]!.meta.frames).toHaveLength(15);
    expect(calls[1]!.meta.batch_seq).toBe(1);
    expect(calls.every((c) => c.n === c.meta.frames.length && c.n <= 30)).toBe(true);
    expect(up.stats()).toEqual({ sent: 45, dropped: 0, failedBatches: 0 });
    await up.flush();
  });

  it("keeps at most MAX_QUEUE frames queued and drops the oldest", async () => {
    const { post, calls } = fakePost();
    const up = uploader(post);
    for (let i = 0; i < MAX_QUEUE + 10; i++) up.push(frame(i));
    expect(up.stats().dropped).toBe(10);
    await up.flush();
    const sent = calls.flatMap((c) => c.meta.frames.map((f) => f.idx));
    expect(sent).toEqual([...Array(MAX_QUEUE).keys()].map((k) => k + 10));
    expect(up.stats()).toEqual({ sent: MAX_QUEUE, dropped: 10, failedBatches: 0 });
  });

  it("loses no frames when one attempt hangs until its timeout while the camera keeps delivering at 30 fps", async () => {
    // The lab failure: one upload stalled, the queue overflowed and ~4 s of frames (idx 88 -> 200) never arrived.
    const { post, calls } = fakePost((_c, k) => (k === 1 ? new Promise<void>(() => undefined) : Promise.resolve()));
    const up = uploader(post);
    let idx = 0;
    const camera = setInterval(() => up.push(frame(idx++)), 33);
    await vi.advanceTimersByTimeAsync(10_000); // 1 s normal, the hung attempt, its retry, the catch-up
    clearInterval(camera);
    await up.flush();
    const sent = calls.slice(0).filter((_c, k) => k !== 1).flatMap((c) => c.meta.frames.map((f) => f.idx));
    expect(up.stats().dropped).toBe(0);
    expect(new Set(sent)).toEqual(new Set([...Array(idx).keys()]));
    expect(calls.every((c) => c.meta.frames.length <= MAX_BATCH)).toBe(true);
  });

  it("drains a backlog in back-to-back batches instead of one per batchMs", async () => {
    const { post, calls } = fakePost();
    const up = uploader(post);
    for (let i = 0; i < 4 * MAX_BATCH; i++) up.push(frame(i));
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls).toHaveLength(4);
    expect(calls.map((c) => c.meta.batch_seq)).toEqual([0, 1, 2, 3]);
    await up.flush();
  });

  it("retries twice then counts a failed batch (network error, 500 ms backoff)", async () => {
    const { post, calls } = fakePost(() => Promise.reject(new TypeError("Failed to fetch")));
    const up = uploader(post);
    for (let i = 0; i < 5; i++) up.push(frame(i));
    const done = up.flush();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(499);
    expect(calls).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(calls).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(500);
    expect(calls).toHaveLength(3);
    await vi.runAllTimersAsync();
    await done;
    expect(calls).toHaveLength(3);
    expect(up.stats()).toEqual({ sent: 0, dropped: 0, failedBatches: 1 });
  });

  it("retries a 5xx and keeps the same batch_seq on every retry", async () => {
    const { post, calls } = fakePost((_c, k) => (k < 2 ? Promise.reject(new ApiError(503, "busy")) : Promise.resolve()));
    const up = uploader(post);
    for (let i = 0; i < 3; i++) up.push(frame(i));
    const done = up.flush();
    await vi.runAllTimersAsync();
    await done;
    for (let i = 3; i < 5; i++) up.push(frame(i));
    const again = up.flush();
    await vi.runAllTimersAsync();
    await again;
    expect(calls.map((c) => c.meta.batch_seq)).toEqual([0, 0, 0, 1]);
    expect(up.stats()).toEqual({ sent: 5, dropped: 0, failedBatches: 0 });
  });

  it("retries a timeout", async () => {
    const { post, calls } = fakePost((_c, k) => (k === 0 ? new Promise<void>(() => undefined) : Promise.resolve()));
    const up = uploader(post, { timeoutMs: 2000 });
    up.push(frame(0));
    const done = up.flush();
    await vi.runAllTimersAsync();
    await done;
    expect(calls).toHaveLength(2);
    expect(up.stats()).toEqual({ sent: 1, dropped: 0, failedBatches: 0 });
  });

  it("never retries a 4xx", async () => {
    const { post, calls } = fakePost(() => Promise.reject(new ApiError(413, "too_many_frames_in_session")));
    const up = uploader(post);
    up.push(frame(0));
    const done = up.flush();
    await vi.runAllTimersAsync();
    await done;
    expect(calls).toHaveLength(1);
    expect(up.stats()).toEqual({ sent: 0, dropped: 0, failedBatches: 1 });
  });

  it("counts a 409 session_complete on a retry as success", async () => {
    const { post, calls } = fakePost((_c, k) =>
      Promise.reject(k === 0 ? new TypeError("Failed to fetch") : new ApiError(409, "session_complete")));
    const up = uploader(post);
    for (let i = 0; i < 4; i++) up.push(frame(i));
    const done = up.flush();
    await vi.runAllTimersAsync();
    await done;
    expect(calls).toHaveLength(2);
    expect(up.stats()).toEqual({ sent: 4, dropped: 0, failedBatches: 0 });
  });

  it("a 409 on the first attempt is a failed batch", async () => {
    const { post, calls } = fakePost(() => Promise.reject(new ApiError(409, "session_complete")));
    const up = uploader(post);
    up.push(frame(0));
    const done = up.flush();
    await vi.runAllTimersAsync();
    await done;
    expect(calls).toHaveLength(1);
    expect(up.stats().failedBatches).toBe(1);
  });

  it("sends one batch at a time, and flush waits for the one in flight", async () => {
    let release!: () => void;
    let inFlight = 0;
    let maxInFlight = 0;
    const { post, calls } = fakePost((_c, k) => {
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      const p = k === 0 ? new Promise<void>((r) => (release = r)) : Promise.resolve();
      return p.finally(() => inFlight--);
    });
    const up = uploader(post);
    for (let i = 0; i < 40; i++) up.push(frame(i));
    await vi.advanceTimersByTimeAsync(1000); // batch 0 goes out and hangs
    expect(calls).toHaveLength(1);
    let flushed = false;
    const done = up.flush().then(() => (flushed = true));
    await vi.advanceTimersByTimeAsync(3000);
    expect(calls).toHaveLength(1); // nothing else while batch 0 is in flight
    expect(flushed).toBe(false);
    release();
    await done;
    expect(calls).toHaveLength(2);
    expect(maxInFlight).toBe(1);
    expect(up.stats()).toEqual({ sent: 40, dropped: 0, failedBatches: 0 });
  });

  it("stop() drops what is queued, sends nothing new and waits for the request in flight", async () => {
    let release!: () => void;
    const { post, calls } = fakePost((_c, k) => (k === 0 ? new Promise<void>((r) => (release = r)) : Promise.resolve()));
    const up = uploader(post);
    for (let i = 0; i < 50; i++) up.push(frame(i));
    await vi.advanceTimersByTimeAsync(1000);
    let stopped = false;
    const done = up.stop().then(() => (stopped = true));
    await vi.advanceTimersByTimeAsync(0);
    expect(stopped).toBe(false);
    release();
    await done;
    await vi.advanceTimersByTimeAsync(5000);
    expect(calls).toHaveLength(1);
    expect(up.stats()).toEqual({ sent: 30, dropped: 20, failedBatches: 0 });
  });

  it("reports the stats after every batch through onStats, so the page can say the connection is weak", async () => {
    const { post } = fakePost((_c, k) => (k < 6 ? Promise.reject(new TypeError("Failed to fetch")) : Promise.resolve()));
    const seen: number[] = [];
    const up = uploader(post, { onStats: (st) => seen.push(st.failedBatches) });
    for (let i = 0; i < 3; i++) {
      up.push(frame(i));
      const done = up.flush();
      await vi.runAllTimersAsync();
      await done;
    }
    expect(seen).toEqual([1, 2, 2]);
    expect(up.stats()).toEqual({ sent: 1, dropped: 0, failedBatches: 2 });
  });
});
