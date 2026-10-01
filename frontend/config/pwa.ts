import type { VitePWAOptions } from "vite-plugin-pwa";

/**
 * PWA options (change 0003, design 6.4; TM-45 / NT3-12).
 *
 * - The service worker precaches the built app shell only.
 * - API and health responses are never served or cached by the service worker:
 *   navigations to /api/ and /health/ bypass the SPA fallback, and there is no
 *   runtime caching.
 * - registerType "prompt" (the default): a new version activates only after every
 *   tab is closed, so an update never reloads a screen mid-task. The in-app
 *   "update available" prompt belongs to the app-shell change (0008).
 */
export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: "prompt",
  injectRegister: "auto",
  includeAssets: ["icons/favicon.svg"],
  manifest: {
    id: "/",
    name: "RMS",
    short_name: "RMS",
    description: "Restaurant management",
    lang: "en",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#ffffff",
    theme_color: "#0f766e",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  },
  workbox: {
    globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
    navigateFallback: "index.html",
    navigateFallbackDenylist: [/^\/api\//, /^\/health\//],
    runtimeCaching: [],
    cleanupOutdatedCaches: true,
  },
};
