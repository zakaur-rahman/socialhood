import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { manifestLink, webManifest as manifest } from "./manifest";

describe("web app manifest (TR-FE-09)", () => {
  it("installs as Amplychat, standalone, opening /app, on Midnight", () => {
    const m = manifest();
    expect(m).toMatchObject({
      name: "Amplychat",
      display: "standalone",
      start_url: "/app",
      background_color: "#131520",
      theme_color: "#131520",
    });
  });

  it("has 192 and 512 px icons and a maskable one, and the files exist", () => {
    const icons = manifest().icons ?? [];
    expect(icons.map((i) => [i.sizes, i.purpose])).toEqual([
      ["192x192", "any"],
      ["512x512", "any"],
      ["512x512", "maskable"],
    ]);
    for (const icon of icons) expect(existsSync(join(process.cwd(), "public", icon.src))).toBe(true);
    // The service worker's notification icon and badge.
    expect(existsSync(join(process.cwd(), "public", "icons", "badge-72.png"))).toBe(true);
    expect(existsSync(join(process.cwd(), "src", "app", "apple-icon.png"))).toBe(true);
  });
});

describe("where the app installs from (C-148)", () => {
  it("one origin: every page links the manifest, from the root layout", () => {
    expect(manifestLink(null)).toEqual({ root: { manifest: "/manifest.webmanifest" }, app: {} });
  });

  it("the app on its own host: only the dashboard's pages link it, so installing happens there", () => {
    // A start_url on another origin than the page is ignored by browsers, so the public site
    // can't point an install at the dashboard; it offers none instead.
    expect(manifestLink("https://dashboard.amplychat.com")).toEqual({ root: {}, app: { manifest: "/manifest.webmanifest" } });
  });
});
