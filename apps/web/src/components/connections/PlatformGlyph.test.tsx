import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { filterCounts, matchesSearch, visibleAccounts } from "@/components/connections/filters";
import { account } from "@/test/api";

import { FacebookGlyph } from "./FacebookGlyph";
import { PLATFORM_BG, PLATFORM_LOGO_BG, PlatformGlyph } from "./PlatformGlyph";

describe("PlatformGlyph (GR-29)", () => {
  it("draws the Facebook mark for a Page, decorative", () => {
    const { container } = render(<PlatformGlyph platform="facebook" className="size-4" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveClass("size-4");
    expect(container.innerHTML).toBe(render(<FacebookGlyph className="size-4" />).container.innerHTML);
  });

  it("keeps the other two marks apart", () => {
    const facebook = render(<PlatformGlyph platform="facebook" />).container.innerHTML;
    const instagram = render(<PlatformGlyph platform="instagram" />).container.innerHTML;
    const whatsapp = render(<PlatformGlyph platform="whatsapp" />).container.innerHTML;
    expect(new Set([facebook, instagram, whatsapp]).size).toBe(3);
  });

  it("fills with the existing facebook colour token", () => {
    expect(PLATFORM_BG.facebook).toBe("bg-facebook");
    expect(PLATFORM_BG.instagram).toBe("bg-instagram");
    expect(PLATFORM_BG.whatsapp).toBe("bg-whatsapp");
  });

  it("has the platforms' logo colours for badges that hold the glyph alone (C-135)", () => {
    expect(PLATFORM_LOGO_BG).toEqual({
      instagram: "bg-instagram-logo-gradient",
      whatsapp: "bg-whatsapp-logo",
      facebook: "bg-facebook-logo",
      web: "bg-web",
    });
  });
});

describe("Connections' search and filters with Pages", () => {
  const page = account({ id: "f1", platform: "facebook", username: "maplebakery", display_name: "Maple Bakery Page" });
  const ig = account({ id: "a1", username: "maple.bakery" });

  it("finds a Page by the word Facebook", () => {
    expect(matchesSearch(page, "facebook")).toBe(true);
    expect(matchesSearch(ig, "facebook")).toBe(false);
    expect(visibleAccounts([ig, page], "all", "Facebook").map((a) => a.id)).toEqual(["f1"]);
  });

  it("counts a Page like any other account", () => {
    expect(filterCounts([ig, page, account({ id: "f2", platform: "facebook", status: "disconnected" })])).toMatchObject({
      all: 3,
      connected: 2,
      disconnected: 1,
    });
  });
});

describe("PlatformGlyph (GR-28)", () => {
  it("draws a different mark for each platform, all decorative", () => {
    const marks = (["instagram", "whatsapp", "web"] as const).map((platform) => {
      const { container, unmount } = render(<PlatformGlyph platform={platform} className="size-4" />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("aria-hidden", "true");
      expect(svg).toHaveClass("size-4");
      const html = svg?.innerHTML ?? "";
      unmount();
      return html;
    });
    expect(new Set(marks).size).toBe(3);
  });

  it("fills each platform's badge from its own token", () => {
    expect(PLATFORM_BG).toEqual({ instagram: "bg-instagram", whatsapp: "bg-whatsapp", facebook: "bg-facebook", web: "bg-web" });
  });
});
