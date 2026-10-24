import { describe, expect, it } from "vitest";

import { assigneeInitials, assigneeName } from "./assignee";

describe("assigneeInitials", () => {
  it("takes the first letter of the first two words", () => {
    expect(assigneeInitials("Priya Nair")).toBe("PN");
    expect(assigneeInitials("  sam   rao  kumar ")).toBe("SR");
  });

  it("uses one letter for one word, and a question mark for nothing", () => {
    expect(assigneeInitials("Kim")).toBe("K");
    expect(assigneeInitials("")).toBe("?");
    expect(assigneeInitials(null)).toBe("?");
  });
});

describe("assigneeName", () => {
  it("prefers the name the API gave", () => {
    expect(assigneeName({ user_id: "u1", name: "Priya" }, [{ user_id: "u1", name: "Other" }])).toBe("Priya");
  });

  it("falls back to the members already loaded, then to a plain word", () => {
    expect(assigneeName({ user_id: "u1", name: null }, [{ user_id: "u1", name: "Priya" }])).toBe("Priya");
    expect(assigneeName({ user_id: "u9", name: null }, [])).toBe("A team member");
  });
});
