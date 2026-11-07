import { describe, expect, it } from "vitest";

import { pageTitle, settingsAreaKey } from "./nav";

describe("Connections and AI apps & API above Settings (C-180)", () => {
  it("marks the item a settings page belongs to", () => {
    expect(settingsAreaKey("/w/maple/settings/connections", "maple")).toBe("connections");
    expect(settingsAreaKey("/w/maple/settings/ai-apps", "maple")).toBe("ai-apps");
    expect(settingsAreaKey("/w/maple/settings/api-keys", "maple")).toBe("ai-apps");
    expect(settingsAreaKey("/w/maple/settings/billing", "maple")).toBe("settings");
    expect(settingsAreaKey("/w/maple/settings", "maple")).toBe("settings");
    expect(settingsAreaKey("/w/maple/inbox", "maple")).toBeNull();
  });

  it("names the phone top bar after that item", () => {
    expect(pageTitle("/w/maple/settings/ai-apps", "maple")).toBe("AI apps & API");
    expect(pageTitle("/w/maple/settings/members", "maple")).toBe("Settings");
    expect(pageTitle("/w/maple/inbox/c1", "maple")).toBe("Inbox");
  });
});
