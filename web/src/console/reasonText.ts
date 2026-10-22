// Plain sentences for the plan's reason codes, shown on the console. Mirrors the mode.* entries of
// server/pulselens/engine/reason_text.py; a pytest fails if they drift apart.
export const MODE_REASON_TEXT: Record<string, string> = {
  "mode.no_flash.requested": "The session runs without flashing light, as requested.",
  "mode.no_flash.too_bright": "The room is too bright for the screen light to matter; the session runs without it.",
  "mode.constrained.fps_too_low_for_light": "The camera is too slow to time the light challenge; only the turn runs.",
  "mode.capable.ok": "The camera, light and face size are good enough for the full challenge.",
  "mode.constrained.fps": "The camera delivers fewer frames than a full challenge needs, so a simpler one runs.",
  "mode.constrained.dim": "The picture is dim, so a simpler, longer challenge runs.",
  "mode.constrained.small_face": "The face is small in the picture, so a simpler, longer challenge runs.",
  "mode.face_not_found": "No face was found before the challenge; the agent should check who is on the call.",
};

export function modeReason(code: string): string {
  return MODE_REASON_TEXT[code] ?? code;
}
