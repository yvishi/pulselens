// Face detection and head yaw with MediaPipe FaceLandmarker (VIDEO mode). Loaded lazily so tests never touch it.
// Assets come from scripts/fetch_web_models.py: /models/face_landmarker.task and /models/wasm.

export interface FaceResult {
  found: boolean;
  /** [x, y, w, h] as fractions of the frame (0..1), so w * h is the face fraction */
  box: [number, number, number, number] | null;
  /** degrees, positive when the person turns to their own left (CONTRACT §1) */
  yawDeg: number | null;
}

export interface FaceTracker {
  detect(video: HTMLVideoElement, tMs: number): FaceResult;
}

export const FACE_MODEL_URL = "/models/face_landmarker.task";
export const FACE_WASM_URL = "/models/wasm";

/**
 * Yaw from MediaPipe's column-major 4x4 facial transformation matrix. Flip YAW_SIGN if the laptop check
 * (turn to your own left, expect positive) shows the opposite sign.
 */
const YAW_SIGN = 1;
export function yawFromMatrix(m: ArrayLike<number>): number {
  return (YAW_SIGN * Math.atan2(m[8]!, m[10]!) * 180) / Math.PI;
}

/** Bounding box of normalised landmarks, clipped to the frame. */
export function boxOf(points: { x: number; y: number }[]): [number, number, number, number] | null {
  if (!points.length) return null;
  const clip = (v: number) => Math.min(1, Math.max(0, v));
  const xs = points.map((p) => clip(p.x));
  const ys = points.map((p) => clip(p.y));
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return [x, y, Math.max(...xs) - x, Math.max(...ys) - y];
}

export async function createFaceTracker(): Promise<FaceTracker> {
  const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(FACE_WASM_URL);
  const make = (delegate: "GPU" | "CPU") =>
    FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: FACE_MODEL_URL, delegate },
      runningMode: "VIDEO",
      numFaces: 1,
      outputFacialTransformationMatrixes: true,
    });
  const landmarker = await make("GPU").catch(() => make("CPU"));
  return {
    detect(video, tMs) {
      try {
        const r = landmarker.detectForVideo(video, tMs);
        const points = r.faceLandmarks[0];
        if (!points?.length) return { found: false, box: null, yawDeg: null };
        const m = r.facialTransformationMatrixes?.[0]?.data;
        return { found: true, box: boxOf(points), yawDeg: m ? yawFromMatrix(m) : null };
      } catch {
        return { found: false, box: null, yawDeg: null };
      }
    },
  };
}
