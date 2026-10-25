import { describe, expect, it } from "vitest";

import { withChoice } from "./PathView";

describe("withChoice", () => {
  it("picks at the first fork", () => {
    expect(withChoice([], 0, 2)).toEqual([2]);
    expect(withChoice([1, 1], 0, 0)).toEqual([0]);
  });

  it("keeps the earlier forks as walked, the first exit where none was chosen", () => {
    // Picking at the second fork before the first was touched must not become the first's choice.
    expect(withChoice([], 1, 1)).toEqual([0, 1]);
    expect(withChoice([2], 2, 1)).toEqual([2, 0, 1]);
  });

  it("drops the choices after the one changed", () => {
    expect(withChoice([1, 1, 1], 1, 0)).toEqual([1, 0]);
  });
});
