import { describe, expect, it } from "vitest";

import { inboxFilterSearch, inboxSearch } from "./url";

describe("inboxSearch", () => {
  it("sets the view and drops it again for all", () => {
    expect(inboxSearch("", { view: "unread" })).toBe("?view=unread");
    expect(inboxSearch("view=unread", { view: "all" })).toBe("");
  });

  it("writes the platform, all included, and keeps other parameters", () => {
    expect(inboxSearch("view=leads", { platform: "all" })).toBe("?view=leads&platform=all");
    expect(inboxSearch("x=1&platform=instagram", { platform: "whatsapp" })).toBe("?x=1&platform=whatsapp");
    expect(inboxSearch("platform=instagram", { platform: null })).toBe("");
  });

  it("leaves untouched what the patch does not name", () => {
    expect(inboxSearch(new URLSearchParams("view=leads&platform=whatsapp"), {})).toBe("?view=leads&platform=whatsapp");
  });
});

describe("inboxFilterSearch", () => {
  it("keeps only view and platform", () => {
    expect(inboxFilterSearch("view=leads&q=x&platform=whatsapp")).toBe("?view=leads&platform=whatsapp");
    expect(inboxFilterSearch("q=x")).toBe("");
  });
});
