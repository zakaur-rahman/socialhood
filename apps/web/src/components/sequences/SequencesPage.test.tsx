import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Sequence } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { sequence } from "./fixtures";
import { SequencesPage } from "./SequencesPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/sequences",
  useSearchParams: () => new URLSearchParams(""),
}));

function setup(items: Sequence[], limits: { active_limit: number | null } = { active_limit: 10 }) {
  return renderWithApi(<SequencesPage />, {
    handlers: {
      "GET /v1/w/:wid/sequences": () =>
        json({ items, active: items.filter((s) => s.status === "active").length, step_limit: 10, ...limits }),
    },
  });
}

describe("the sequences list (GR-24)", () => {
  it("says there are none and offers to make one", async () => {
    setup([]);
    expect(await screen.findByText("No sequences yet")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /New/ }).length).toBeGreaterThan(0);
  });

  it("shows what starts each one, its steps and where its people are", async () => {
    setup([sequence(), sequence({ id: "s2", name: "After the sale", status: "paused", step_count: 1, enrolments: { active: 0, completed: 0, stopped: 0 } })]);
    const rows = await screen.findAllByTestId("sequence-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByRole("link", { name: "Welcome follow-up" })).toHaveAttribute("href", "/w/maple/sequences/s1");
    expect(rows[0]).toHaveTextContent("Starts when: A tag is added: Follow up");
    expect(rows[0]).toHaveTextContent("3 steps");
    expect(rows[0]).toHaveTextContent("4 in it · 2 finished · 1 stopped");
    expect(within(rows[0]).getByText("On")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Paused")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("1 step");
  });

  it("names how many sequences the plan lets run", async () => {
    setup([sequence()], { active_limit: 1 });
    expect(await screen.findByTestId("sequence-limits")).toHaveTextContent("1 of 1 sequence on in your plan.");
  });

  it("shows why a sequence can't run", async () => {
    setup([sequence({ status: "paused", problems: ["The tag that starts this sequence was deleted. Choose another."] })]);
    expect(await screen.findByText(/tag that starts this sequence was deleted/)).toBeInTheDocument();
  });
});
