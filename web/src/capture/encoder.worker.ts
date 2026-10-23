// Encodes ImageBitmaps to JPEG off the main thread (see encoder.ts).

interface EncodeRequest {
  id: number;
  bitmap: ImageBitmap;
  quality: number;
}

const scope = self as unknown as {
  onmessage: ((e: MessageEvent<EncodeRequest>) => void) | null;
  postMessage(message: unknown): void;
};

const canvases = new Map<string, OffscreenCanvas>();

scope.onmessage = async (e) => {
  const { id, bitmap, quality } = e.data;
  try {
    const key = `${bitmap.width}x${bitmap.height}`;
    let canvas = canvases.get(key);
    if (!canvas) {
      canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      canvases.set(key, canvas);
    }
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0);
    bitmap.close();
    const blob = await canvas.convertToBlob({ type: "image/jpeg", quality });
    scope.postMessage({ id, blob });
  } catch (err) {
    scope.postMessage({ id, error: String(err) });
  }
};
