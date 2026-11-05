import { describe, expect, it } from "vitest";

import { waitingFirst, waitingLine, waitingTitle } from "./approval";

describe("waitingFirst", () => {
  it("moves waiting sources up, keeps the order otherwise, and leaves the input alone", () => {
    const items = [
      { id: "a", status: "ready" },
      { id: "b", status: "awaiting_approval" },
      { id: "c", status: "failed" },
      { id: "d", status: "awaiting_approval" },
    ] as const;
    expect(waitingFirst(items).map((item) => item.id)).toEqual(["b", "d", "a", "c"]);
    expect(items[0].id).toBe("a");
  });
});

describe("the count's wording", () => {
  it("is singular for one and plural otherwise", () => {
    expect(waitingLine(1)).toBe("1 from an AI app is waiting for approval.");
    expect(waitingLine(2)).toBe("2 from AI apps are waiting for approval.");
    expect(waitingTitle(1)).toBe("1 source from an AI app is waiting for approval");
    expect(waitingTitle(12)).toBe("12 sources from AI apps are waiting for approval");
  });
});
