import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import manifest from "./manifest";

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
