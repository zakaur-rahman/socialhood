import { describe, expect, it } from "vitest";

import { cx } from "./cx";

describe("cx", () => {
  it("joins the classes it is given and skips the empty ones", () => {
    expect(cx("a b", undefined, "c", false, null, "", "d")).toBe("a b c d");
    expect(cx()).toBe("");
  });
});
