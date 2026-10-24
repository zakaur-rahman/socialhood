import { describe, expect, it } from "vitest";

import { bestTimes } from "@/test/composer-fixtures";

import { basis, clock, dayTimeLabel, nextDateFor, notEnoughHistory, suggestionFor, topSuggestions, weekdayOf } from "./best-times";

describe("best times helpers (GR-30)", () => {
  it("numbers weekdays from Monday", () => {
    expect(weekdayOf("2026-10-26")).toBe(0); // a Monday
    expect(weekdayOf("2026-10-25")).toBe(6); // a Sunday
    expect(weekdayOf("nonsense")).toBeNull();
  });

  it("finds the next date on a weekday, today included", () => {
    expect(nextDateFor(0, "2026-10-24")).toBe("2026-10-26"); // Saturday -> Monday
    expect(nextDateFor(5, "2026-10-24")).toBe("2026-10-24"); // today is Saturday
    expect(nextDateFor(4, "2026-10-31")).toBe("2026-11-06");
  });

  it("reads a suggestion only with enough history and a time for the day", () => {
    const data = bestTimes();
    expect(suggestionFor(data, 0)?.local_time).toBe("18:00:00");
    expect(suggestionFor(data, 1)).toBeNull();
    expect(suggestionFor(data, null)).toBeNull();
    expect(suggestionFor(bestTimes({ enough_history: false }), 0)).toBeNull();
  });

  it("lists the best days first", () => {
    const data = bestTimes();
    expect(topSuggestions(data, 3).map(dayTimeLabel)).toEqual(["Mon 18:00", "Wed 12:00"]);
    expect(topSuggestions(bestTimes({ enough_history: false }), 3)).toEqual([]);
  });

  it("words the basis and the missing history", () => {
    const [monday] = bestTimes().days;
    expect(basis(monday)).toBe("12 posts, 34% above a typical post");
    expect(basis({ ...monday, posts: 1, lift_percent: -10 })).toBe("1 post, 10% below a typical post");
    expect(basis({ ...monday, lift_percent: null })).toBe("12 posts");
    expect(notEnoughHistory(bestTimes({ enough_history: false, sample_size: 3, min_posts: 10 }))).toBe(
      "Not enough history for best times yet: 3 of 10 posts with engagement.",
    );
    expect(clock("18:00:00")).toBe("18:00");
  });
});
