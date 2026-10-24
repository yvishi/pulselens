/**
 * Frame grabber. One clock (CONTRACT section 1): frame time = captureTime ?? expectedDisplayTime ?? callback now,
 * all in the performance.now() domain, sent as t_ms = time - t0.
 *
 * - rvfc (preferred): video.requestVideoFrameCallback with its metadata.
 * - videoframe (opt-in, Chrome): MediaStreamTrackProcessor; VideoFrame.timestamp mapped once to now().
 * - raf (fallback): requestAnimationFrame, a new frame when the decoded-frame count changes.
 *
 * Each frame is scaled to fit `size` and JPEG-encoded as delivered (no filters). Frames whose time does not move
 * forward are skipped, so idx and t_ms strictly increase. Frames reach onFrame in idx order.
 *
 * fpsOver(ms) is the recent frame rate (frames in the last ms), for the Y9 fps-drop downgrade.
 */
import { now } from "./clock";
import { createEncoder, type FrameEncoder } from "./encoder";
import { frameTime, type FrameClock } from "./util";

export interface GrabbedFrame {
  idx: number;
  t_ms: number;
  w: number;
  h: number;
  jpeg: Blob;
}

export type { FrameClock } from "./util";
export type GrabberSource = "auto" | "rvfc" | "videoframe" | "raf";

export interface GrabberOptions {
  size: [number, number];
  jpegQuality: number;
  t0: number;
  onFrame: (f: GrabbedFrame) => void;
  source?: GrabberSource;
  encoder?: FrameEncoder; // injectable for tests
  now?: () => number; // injectable for tests; performance.now() by default
}

export interface GrabberStats {
  frames: number;
  medianFps: number; // 0 until two frames
  droppedRatio: number; // 0..1, from presentedFrames gaps
  clock: FrameClock; // source of the latest frame's time
}

interface VideoFrameLike {
  timestamp: number; // microseconds
  close(): void;
}
type ProcessorCtor = new (init: { track: MediaStreamTrack }) => { readable: ReadableStream<VideoFrameLike> };

const MAX_INTERVALS = 300;
/** Frame times kept for fpsOver: 5 s at 60 fps. */
const MAX_TIMES = 300;

/** Fits (w, h) inside a box of the same orientation, keeping aspect and never upscaling. */
export function fitSize(w: number, h: number, box: readonly [number, number]): [number, number] {
  const [bw, bh] = w >= h ? box : [box[1], box[0]];
  const s = Math.min(1, bw / w, bh / h);
  return [Math.max(1, Math.round(w * s)), Math.max(1, Math.round(h * s))];
}

export class FrameGrabber {
  private running = false;
  private idx = 0;
  private lastT = -Infinity;
  private intervals: number[] = [];
  private lastPresented: number | null = null;
  private presented = 0;
  private dropped = 0;
  private clock: FrameClock = "now";
  private startedAt: number | null = null;
  private times: number[] = [];
  private chain: Promise<void> = Promise.resolve();
  private stopVideoFrame?: () => void;
  private readonly encoder: FrameEncoder;

  constructor(
    private readonly video: HTMLVideoElement,
    private readonly opts: GrabberOptions,
  ) {
    this.encoder = opts.encoder ?? createEncoder();
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.startedAt = (this.opts.now ?? now)();
    const source = this.opts.source ?? "auto";
    const hasRvfc = "requestVideoFrameCallback" in this.video;
    const Processor = (globalThis as unknown as { MediaStreamTrackProcessor?: ProcessorCtor }).MediaStreamTrackProcessor;
    if (source === "videoframe" && Processor) this.runVideoFrame(Processor);
    else if ((source === "auto" || source === "rvfc") && hasRvfc) this.runRvfc();
    else this.runRaf();
  }

  stop(): void {
    this.running = false;
    this.stopVideoFrame?.();
  }

  close(): void {
    this.stop();
    this.encoder.close();
  }

  stats(): GrabberStats {
    const xs = [...this.intervals].sort((a, b) => a - b);
    const median = xs.length ? xs[Math.floor(xs.length / 2)]! : 0;
    const total = this.presented + this.dropped;
    return {
      frames: this.idx,
      medianFps: median > 0 ? 1000 / median : 0,
      droppedRatio: total ? this.dropped / total : 0,
      clock: this.clock,
    };
  }

  /**
   * Frames per second over the last `ms` (frame times in the performance.now() domain), or null until the grabber
   * has run for `ms`. A frozen stream reads 0.
   */
  fpsOver(ms: number): number | null {
    if (this.startedAt === null) return null;
    const at = (this.opts.now ?? now)();
    if (at - this.startedAt < ms) return null;
    const from = at - ms;
    let n = 0;
    for (let k = this.times.length - 1; k >= 0 && this.times[k]! >= from; k--) n++;
    return (n * 1000) / ms;
  }

  private runRvfc(): void {
    const loop = (cbNow: number, md: VideoFrameCallbackMetadata) => {
      if (!this.running) return;
      const { t, clock } = frameTime(md, cbNow);
      this.grab(this.video, t, clock, md.presentedFrames ?? null);
      this.video.requestVideoFrameCallback(loop);
    };
    this.video.requestVideoFrameCallback(loop);
  }

  private runRaf(): void {
    let lastCount = -1;
    let lastTime = -1;
    const loop = (ts: number) => {
      if (!this.running) return;
      const count = this.video.getVideoPlaybackQuality?.().totalVideoFrames;
      const fresh = count !== undefined && count > 0 ? count !== lastCount : this.video.currentTime !== lastTime;
      lastCount = count ?? -1;
      lastTime = this.video.currentTime;
      if (fresh && this.video.readyState >= 2) this.grab(this.video, ts, "now", null);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  private runVideoFrame(Processor: ProcessorCtor): void {
    const stream = this.video.srcObject as MediaStream;
    const track = stream.getVideoTracks()[0]!.clone();
    const reader = new Processor({ track }).readable.getReader();
    let offset: number | null = null;
    this.stopVideoFrame = () => {
      void reader.cancel();
      track.stop();
    };
    void (async () => {
      while (this.running) {
        const { value: frame, done } = await reader.read();
        if (done || !frame) break;
        const ts = frame.timestamp / 1000;
        offset ??= now() - ts; // mapped once into the performance.now() domain
        this.grab(frame as unknown as CanvasImageSource, ts + offset, "now", null);
        frame.close();
      }
    })();
  }

  private grab(source: CanvasImageSource, t: number, clock: FrameClock, presented: number | null): void {
    if (t <= this.lastT) return;
    const vw = this.video.videoWidth;
    const vh = this.video.videoHeight;
    if (!vw || !vh) return;
    if (Number.isFinite(this.lastT)) {
      this.intervals.push(t - this.lastT);
      if (this.intervals.length > MAX_INTERVALS) this.intervals.shift();
    }
    this.lastT = t;
    this.times.push(t);
    if (this.times.length > MAX_TIMES) this.times.shift();
    this.clock = clock;
    if (presented !== null) {
      if (this.lastPresented !== null && presented > this.lastPresented) this.dropped += presented - this.lastPresented - 1;
      this.presented++;
      this.lastPresented = presented;
    }
    const idx = this.idx++;
    const [w, h] = fitSize(vw, vh, this.opts.size);
    const t_ms = t - this.opts.t0;
    const jpeg = this.encoder.encode(source, w, h, this.opts.jpegQuality);
    // Emit in idx order; a frame that fails to encode is dropped, never thrown into the capture loop.
    this.chain = this.chain.then(() =>
      jpeg.then(
        (blob) => this.opts.onFrame({ idx, t_ms, w, h, jpeg: blob }),
        (e) => console.warn(`frame ${idx} encode failed`, e),
      ),
    );
  }
}
