import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The server runs on :8000; the browser only talks to this origin, so a cloudflared tunnel needs one URL and no CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: [".trycloudflare.com"],
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
