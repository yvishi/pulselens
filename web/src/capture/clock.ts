/**
 * The one clock (CONTRACT section 1). Every client timestamp is performance.now() in ms, or a frame time
 * mapped into that domain, and goes on the wire as ms since t0. Never use Date.now().
 */
export const now = (): number => performance.now();
