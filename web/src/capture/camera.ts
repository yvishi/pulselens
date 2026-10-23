// Camera open and close: getUserMedia with the capture constraints, attached to a playing <video>.

export interface OpenCamera {
  stream: MediaStream;
  track: MediaStreamTrack;
  settings: MediaTrackSettings;
}

/** getUserMedia for the front camera at `size` (ideal, 30 fps), attached to `video` and playing. */
export async function openCamera(video: HTMLVideoElement, size: [number, number]): Promise<OpenCamera> {
  const [w, h] = size;
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: w }, height: { ideal: h }, frameRate: { ideal: 30 }, facingMode: "user" },
    audio: false,
  });
  video.muted = true;
  video.playsInline = true;
  video.srcObject = stream;
  await video.play();
  if (!video.videoWidth) await new Promise((r) => video.addEventListener("loadedmetadata", r, { once: true }));
  const track = stream.getVideoTracks()[0]!;
  return { stream, track, settings: track.getSettings() };
}

export function stopCamera(cam: OpenCamera | null, video?: HTMLVideoElement): void {
  for (const t of cam?.stream.getTracks() ?? []) t.stop();
  if (video) video.srcObject = null;
}
