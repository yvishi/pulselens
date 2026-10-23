/**
 * JPEG encoding off the capture path. With OffscreenCanvas + workers, the frame is scaled into an ImageBitmap on
 * the main thread (synchronously, so it is the frame the callback saw) and encoded in a worker. Otherwise a
 * main-thread canvas is drawn synchronously and toBlob encodes it in the background. Plain drawImage: no filters.
 */

export interface FrameEncoder {
  /** Snapshots `source` at w x h now (synchronously) and resolves with its JPEG later. */
  encode(source: CanvasImageSource, w: number, h: number, quality: number): Promise<Blob>;
  close(): void;
}

class MainThreadEncoder implements FrameEncoder {
  private readonly canvases = new Map<string, HTMLCanvasElement>();

  encode(source: CanvasImageSource, w: number, h: number, quality: number): Promise<Blob> {
    const key = `${w}x${h}`;
    let canvas = this.canvases.get(key);
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      this.canvases.set(key, canvas);
    }
    canvas.getContext("2d")!.drawImage(source, 0, 0, w, h);
    return new Promise((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/jpeg", quality),
    );
  }

  close(): void {
    this.canvases.clear();
  }
}

class WorkerEncoder implements FrameEncoder {
  private readonly worker: Worker;
  private readonly canvases = new Map<string, OffscreenCanvas>();
  private readonly pending = new Map<number, { resolve: (b: Blob) => void; reject: (e: Error) => void }>();
  private nextId = 0;

  constructor() {
    this.worker = new Worker(new URL("./encoder.worker.ts", import.meta.url), { type: "module" });
    this.worker.onmessage = (e: MessageEvent<{ id: number; blob?: Blob; error?: string }>) => {
      const p = this.pending.get(e.data.id);
      this.pending.delete(e.data.id);
      if (e.data.blob) p?.resolve(e.data.blob);
      else p?.reject(new Error(e.data.error ?? "encode failed"));
    };
  }

  encode(source: CanvasImageSource, w: number, h: number, quality: number): Promise<Blob> {
    const key = `${w}x${h}`;
    let canvas = this.canvases.get(key);
    if (!canvas) {
      canvas = new OffscreenCanvas(w, h);
      this.canvases.set(key, canvas);
    }
    canvas.getContext("2d")!.drawImage(source, 0, 0, w, h);
    const bitmap = canvas.transferToImageBitmap();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, bitmap, quality }, [bitmap]);
    });
  }

  close(): void {
    this.worker.terminate();
    for (const p of this.pending.values()) p.reject(new Error("encoder closed"));
    this.pending.clear();
  }
}

/** Worker encoder when Worker and OffscreenCanvas exist, else the main-thread canvas. */
export function createEncoder(prefer: "auto" | "main" = "auto"): FrameEncoder {
  if (prefer === "auto" && typeof Worker !== "undefined" && typeof OffscreenCanvas !== "undefined") {
    try {
      return new WorkerEncoder();
    } catch (e) {
      console.warn("Worker encoder unavailable, encoding on the main thread", e);
    }
  }
  return new MainThreadEncoder();
}
