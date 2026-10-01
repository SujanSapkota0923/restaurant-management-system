/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { pwaOptions } from "./config/pwa.ts";

/** The frontend/ directory itself. Env files are read only from here (SC-41). */
export const frontendDir = fileURLToPath(new URL(".", import.meta.url));

/** Django dev server. Requests keep the original Host header so dev is same-origin (C6-1). */
const backendOrigin = "http://127.0.0.1:8000";

export default defineConfig({
  // SC-41: never the repository root, which holds the backend env file.
  envDir: frontendDir,
  envPrefix: "VITE_",
  plugins: [react(), tailwindcss(), VitePWA(pwaOptions)],
  server: {
    // SC-42: loopback only, never the LAN.
    host: "localhost",
    port: 5173,
    strictPort: true,
    fs: { strict: true },
    proxy: {
      "/api": { target: backendOrigin, changeOrigin: false },
      "/health": { target: backendOrigin, changeOrigin: false },
    },
  },
  preview: {
    host: "localhost",
    port: 4173,
    strictPort: true,
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "config/**/*.test.ts"],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
