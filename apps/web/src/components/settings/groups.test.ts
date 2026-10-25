import { describe, expect, it } from "vitest";

import { filterGroups, SEGMENT_META, SETTINGS_GROUPS, visibleGroups } from "./groups";
import { SETTINGS_SECTIONS } from "./sections";

describe("settings groups", () => {
  it("every settings section has group metadata and sits in a group", () => {
    const grouped = new Set(SETTINGS_GROUPS.flatMap((g) => g.segments));
    for (const section of SETTINGS_SECTIONS) {
      expect(SEGMENT_META[section.segment], section.segment).toBeDefined();
      expect(grouped.has(section.segment), section.segment).toBe(true);
    }
  });

  it("keeps role filtering and drops empty groups", () => {
    const agent = visibleGroups("agent");
    expect(agent.flatMap((g) => g.items.map((i) => i.segment))).not.toContain("billing");
    expect(agent.map((g) => g.id)).not.toContain("admin");
    expect(visibleGroups("owner").map((g) => g.id)).toContain("admin");
  });

  it("puts a section named in no group under More", () => {
    const groups = visibleGroups("owner", [...SETTINGS_SECTIONS, { segment: "zzz", label: "Zzz", roles: ["owner"] }]);
    expect(groups.at(-1)).toMatchObject({
      id: "more",
      items: [{ segment: "zzz" }],
    });
  });

  it("filters by label and keyword, any case", () => {
    const groups = visibleGroups("owner");
    expect(filterGroups(groups, "SPAM").flatMap((g) => g.items.map((i) => i.segment))).toEqual(["ai"]);
    expect(filterGroups(groups, "plan").flatMap((g) => g.items.map((i) => i.segment))).toEqual(["billing"]);
    expect(filterGroups(groups, "nothing-here")).toEqual([]);
  });
});
