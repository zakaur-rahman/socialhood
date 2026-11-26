import { describe, expect, it } from "vitest";

import { FOOT_NAV, footSegment, pageTitle } from "./nav";

describe("Connections above Settings (C-180)", () => {
  it("is its own page, like Inbox, not a settings page", () => {
    expect(FOOT_NAV.map((item) => [item.label, item.href("maple")])).toEqual([
      ["Connections", "/w/maple/connections"],
      ["MCP & API", "/w/maple/settings/ai-apps"],
      ["Settings", "/w/maple/settings"],
    ]);
  });

  it("lights MCP & API on its page and Settings on the others (C-208)", () => {
    expect(footSegment("/w/maple/settings/ai-apps", "maple")).toBe("settings/ai-apps");
    expect(footSegment("/w/maple/settings/billing", "maple")).toBe("settings");
    expect(footSegment("/w/maple/connections", "maple")).toBe("connections");
  });

  it("names the phone top bar", () => {
    expect(pageTitle("/w/maple/connections", "maple")).toBe("Connections");
    expect(pageTitle("/w/maple/settings/ai-apps", "maple")).toBe("Settings");
    expect(pageTitle("/w/maple/inbox/c1", "maple")).toBe("Inbox");
  });
});
