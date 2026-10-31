import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import FaqPage from "@/app/(marketing)/faq/page";
import { STATUS_LABEL, GTM_PAGES, COMPARE_WATI, FEATURE_PUBLISHING } from "@/lib/marketing/gtm-pages";
import { FAQ_GROUPS } from "@/lib/marketing/faq";
import { MATRIX } from "@/lib/marketing/plan-matrix";
import { FOR_BUSINESSES, FOR_CREATORS } from "@/lib/marketing/solutions";

import { GtmPageView } from "./GtmPageView";
import { CARD_ICONS, FAQ_GROUP_ICONS, MATRIX_GROUP_ICONS } from "./page-icons";
import { PlanMatrix } from "./PlanMatrix";

/** C-159: the product pages' premium layout keeps every word, and gives every card its icon. */
describe("the product pages' icons (C-159)", () => {
  it("every card on the go-to-market and audience pages has its own icon", () => {
    const titles = [
      ...GTM_PAGES.flatMap((page) => page.blocks.filter((block) => block.id !== "choose").flatMap((block) => block.items.map((item) => item.title))),
      ...[FOR_CREATORS, FOR_BUSINESSES].flatMap((page) => page.features.map((feature) => feature.title)),
    ];
    const missing = titles.filter((title) => !CARD_ICONS[title]);
    expect(missing).toEqual([]);
  });

  it("every FAQ group and plan-limit group has an icon", () => {
    for (const group of FAQ_GROUPS) expect(FAQ_GROUP_ICONS[group.id], group.id).toBeDefined();
    for (const group of MATRIX) expect(MATRIX_GROUP_ICONS[group.id], group.id).toBeDefined();
  });
});

describe("a comparison page (C-159)", () => {
  it("shows the verdict as two cards and each status as a chip with the same words", () => {
    const { container } = render(<GtmPageView page={COMPARE_WATI} />);
    expect(container.querySelectorAll(".verdict > .vcard")).toHaveLength(2);
    expect(container.querySelectorAll(".vcard.is-ours")).toHaveLength(1);
    const table = screen.getByRole("table", { name: "Amplychat and Wati feature by feature" });
    const chips = table.querySelectorAll("[data-status]");
    expect(chips).toHaveLength(COMPARE_WATI.compare!.rows.length * 2);
    for (const chip of chips) expect(chip.textContent).toBe(STATUS_LABEL[chip.getAttribute("data-status") as keyof typeof STATUS_LABEL]);
    // Our column is marked in the header and in every row.
    expect(table.querySelectorAll("thead th.ours")).toHaveLength(1);
    expect(table.querySelectorAll("tbody td.ours")).toHaveLength(COMPARE_WATI.compare!.rows.length);
    // The sources and the trademark note sit in one footnote card.
    const footnote = container.querySelector(".fnote") as HTMLElement;
    expect(within(footnote).getByRole("list", { name: "Sources" })).toBeInTheDocument();
    expect(footnote).toHaveTextContent(/Wati is a trademark of its owner/);
    // The head's side card links to the page's sections.
    const toc = within(screen.getByRole("navigation", { name: "On this page" }));
    expect(toc.getByRole("link", { name: "Side by side" })).toHaveAttribute("href", "#side-by-side");
  });

  it("a feature page shows its own steps (C-163, in place of the site's three) and the closing band", () => {
    render(<GtmPageView page={FEATURE_PUBLISHING} />);
    expect(screen.queryByRole("region", { name: "Set up in three steps" })).not.toBeInTheDocument();
    const steps = within(screen.getByRole("region", { name: "How it works" }));
    expect(steps.getAllByRole("listitem")).toHaveLength(FEATURE_PUBLISHING.feature!.steps.length);
    expect(screen.getByRole("heading", { level: 2, name: "Ready to take control of every conversation?" })).toBeInTheDocument();
  });
});

describe("the pricing limits (C-159)", () => {
  it("marks Included and Not included as chips, and keeps every caption", () => {
    const { container } = render(<PlanMatrix />);
    for (const group of MATRIX) expect(screen.getByRole("table", { name: group.title })).toBeInTheDocument();
    for (const chip of container.querySelectorAll(".chip")) expect(["Included", "Not included"]).toContain(chip.textContent);
    expect(container.querySelectorAll("col.c-feat")).toHaveLength(MATRIX.length);
  });
});

describe("/faq (C-159)", () => {
  it("has a group nav linking to every group, each group headed by its icon", () => {
    render(<FaqPage />);
    const nav = within(screen.getByRole("navigation", { name: "Question groups" }));
    for (const group of FAQ_GROUPS) {
      expect(nav.getByRole("link", { name: new RegExp(`^${group.title}`) })).toHaveAttribute("href", `#${group.id}`);
      const heading = screen.getByRole("heading", { level: 2, name: group.title });
      expect(heading.querySelector(".ico svg")).not.toBeNull();
    }
  });
});

describe("site.css (C-159)", () => {
  it("keeps the product pages' styles in their own delimited block", () => {
    const css = readFileSync(join(process.cwd(), "src/components/site/site.css"), "utf8");
    const start = css.indexOf("/* ==== C-159 product ==== */");
    const end = css.indexOf("/* ==== end C-159 product ==== */");
    expect(start).toBeGreaterThan(0);
    expect(end).toBeGreaterThan(start);
  });
});
