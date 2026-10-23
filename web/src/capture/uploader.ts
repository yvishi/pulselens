/**
 * Batched frame upload (CONTRACT section 2, row 5). Every batchMs the head of the queue (<= 30 frames) goes out as
 * one multipart postFrames call. The queue holds <= 90 frames; on overflow the oldest is dropped and counted, so
 * capture never blocks. One batch is in flight at a time, in idx order.
 *
 * Retries: a batch keeps its batch_seq on every attempt and is retried twice (500 ms apart) only after a network
 * error, a 5xx or a timeout, never after a 4xx. A 409 `session_complete` on a retry means an earlier attempt did
 * land before the session completed, so it counts as sent.
 */
import { ApiError, postFrames } from "../api/client";
import type { FrameBatchMeta } from "../contracts";
import { sleep as realSleep } from "./flash";
import type { GrabbedFrame } from "./grabber";

export type PostFrames = (id: string, token: string, meta: FrameBatchMeta, jpegs: Blob[]) => Promise<void>;

export interface UploaderOptions {
  sessionId: string;
  token: string;
  batchMs: number;
  /** injectable for tests; defaults to the API client's postFrames */
  postFrames?: PostFrames;
  sleep?: (ms: number) => Promise<void>;
  /** one attempt's timeout */
  timeoutMs?: number;
}

export interface UploaderStats {
  /** frames the server accepted */
  sent: number;
  /** frames dropped from a full queue (or by stop()) */
  dropped: number;
  /** batches given up on after their retries (or refused with a 4xx) */
  failedBatches: number;
}

export const MAX_BATCH = 30;
export const MAX_QUEUE = 90;
export const RETRIES = 2;
export const RETRY_BACKOFF_MS = 500;
export const ATTEMPT_TIMEOUT_MS = 10_000;

class Timeout extends Error {}

/** Whether a failed attempt may be retried: network errors, 5xx and timeouts, never a 4xx. */
export function retryable(e: unknown): boolean {
  return !(e instanceof ApiError) || e.status >= 500;
}

export class FrameUploader {
  private queue: GrabbedFrame[] = [];
  private seq = 0;
  private timer: ReturnType<typeof setInterval> | undefined;
  /** the serial send chain: every batch runs after the previous one settles */
  private chain: Promise<void> = Promise.resolve();
  private busy = false;
  private stopped = false;
  private readonly counts: UploaderStats = { sent: 0, dropped: 0, failedBatches: 0 };
  private readonly post: PostFrames;
  private readonly sleep: (ms: number) => Promise<void>;

  constructor(private readonly opts: UploaderOptions) {
    this.post = opts.postFrames ?? postFrames;
    this.sleep = opts.sleep ?? realSleep;
  }

  push(f: GrabbedFrame): void {
    if (this.stopped) {
      this.counts.dropped++;
      return;
    }
    this.queue.push(f);
    while (this.queue.length > MAX_QUEUE) {
      this.queue.shift();
      this.counts.dropped++;
    }
    this.timer ??= setInterval(() => this.tick(), this.opts.batchMs);
  }

  stats(): UploaderStats {
    return { ...this.counts };
  }

  /** Sends everything queued; resolves when the queue is empty and nothing is in flight. */
  async flush(): Promise<void> {
    this.clearTimer();
    for (;;) {
      await this.chain;
      if (!this.queue.length || this.stopped) return;
      this.enqueueSend();
    }
  }

  /** Gives up: drops the queue, sends nothing new, and resolves once the request in flight (if any) settles. */
  async stop(): Promise<void> {
    this.stopped = true;
    this.clearTimer();
    this.counts.dropped += this.queue.length;
    this.queue = [];
    await this.chain;
  }

  private clearTimer(): void {
    clearInterval(this.timer);
    this.timer = undefined;
  }

  private tick(): void {
    if (this.busy || !this.queue.length) return; // a slow batch: the next tick picks up the backlog
    this.enqueueSend();
  }

  private enqueueSend(): void {
    this.chain = this.chain.then(() => this.sendNext());
  }

  private async sendNext(): Promise<void> {
    if (this.stopped || !this.queue.length) return;
    const batch = this.queue.splice(0, MAX_BATCH);
    const meta: FrameBatchMeta = {
      batch_seq: this.seq++,
      frames: batch.map(({ idx, t_ms, w, h }) => ({ idx, t_ms, w, h })),
    };
    this.busy = true;
    try {
      if (await this.sendWithRetries(meta, batch.map((f) => f.jpeg))) this.counts.sent += batch.length;
      else this.counts.failedBatches++;
    } finally {
      this.busy = false;
    }
  }

  /** True once the server has the batch. The same meta (and batch_seq) goes out on every attempt. */
  private async sendWithRetries(meta: FrameBatchMeta, jpegs: Blob[]): Promise<boolean> {
    for (let attempt = 0; ; attempt++) {
      try {
        await this.withTimeout(this.post(this.opts.sessionId, this.opts.token, meta, jpegs));
        return true;
      } catch (e) {
        if (attempt > 0 && e instanceof ApiError && e.status === 409 && e.detail === "session_complete") return true;
        if (!retryable(e) || attempt >= RETRIES || this.stopped) {
          console.warn(`frame batch ${meta.batch_seq} failed`, e);
          return false;
        }
      }
      await this.sleep(RETRY_BACKOFF_MS);
    }
  }

  private withTimeout<T>(p: Promise<T>): Promise<T> {
    const ms = this.opts.timeoutMs ?? ATTEMPT_TIMEOUT_MS;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Timeout(`upload attempt timed out after ${ms} ms`)), ms);
    });
    return Promise.race([p, timeout]).finally(() => clearTimeout(timer));
  }
}
