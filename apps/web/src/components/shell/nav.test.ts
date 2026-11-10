import { describe, expect, it } from "vitest";

import { FOOT_NAV, pageTitle } from "./nav";

describe("Connections above Settings (C-180)", () => {
  it("is its own page, like Inbox, not a settings page", () => {
    expect(FOOT_NAV.map((item) => [item.label, item.href("maple")])).toEqual([
      ["Connections", "/w/maple/connections"],
      ["Settings", "/w/maple/settings"],
    ]);
  });

  it("names the phone top bar", () => {
    expect(pageTitle("/w/maple/connections", "maple")).toBe("Connections");
    expect(pageTitle("/w/maple/settings/ai-apps", "maple")).toBe("Settings");
    expect(pageTitle("/w/maple/inbox/c1", "maple")).toBe("Inbox");
  });
});
