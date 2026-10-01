// @vitest-environment node
import { describe, expect, it } from "vitest";
import viteConfig, { frontendDir } from "../vite.config.ts";
import { pwaOptions } from "./pwa.ts";

describe("PWA config (NT3-12, TM-45)", () => {
  const workbox = pwaOptions.workbox ?? {};
  const denylist = workbox.navigateFallbackDenylist ?? [];

  it("never serves the SPA fallback for /api/ or /health/ navigations", () => {
    for (const path of ["/api/", "/api/v1/me", "/health/", "/health/ready"]) {
      expect(denylist.some((re) => re.test(path))).toBe(true);
    }
    expect(denylist.some((re) => re.test("/r/abc/orders"))).toBe(false);
  });

  it("has no runtime caching (so nothing under /api/ is cached)", () => {
    expect(workbox.runtimeCaching ?? []).toEqual([]);
  });

  it("precaches only static app-shell assets", () => {
    for (const pattern of workbox.globPatterns ?? []) {
      expect(pattern).not.toMatch(/api|health|json\b/);
    }
  });

  it("has an installable manifest", () => {
    const manifest = pwaOptions.manifest;
    if (manifest === false || manifest === undefined) throw new Error("manifest missing");
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/");
    const icons = manifest.icons ?? [];
    expect(icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(icons.some((i) => i.purpose === "maskable")).toBe(true);
  });
});

describe("Vite config (SC-41, SC-42)", () => {
  it("reads env files only from frontend/", () => {
    expect(viteConfig.envDir).toBe(frontendDir);
    expect(frontendDir).toMatch(/[/\\]frontend[/\\]$/);
    expect(viteConfig.envPrefix).toBe("VITE_");
  });

  it("binds the dev and preview servers to loopback with strict fs", () => {
    expect(viteConfig.server?.host).toBe("localhost");
    expect(viteConfig.server?.fs?.strict).toBe(true);
    expect(viteConfig.preview?.host).toBe("localhost");
  });

  it("proxies /api and /health to the local backend preserving Host", () => {
    const proxy = viteConfig.server?.proxy ?? {};
    for (const prefix of ["/api", "/health"]) {
      const entry = proxy[prefix];
      if (entry === undefined || typeof entry === "string") throw new Error(`${prefix} proxy`);
      expect(entry.target).toBe("http://127.0.0.1:8000");
      expect(entry.changeOrigin).toBe(false);
    }
  });
});
