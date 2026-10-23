import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KnowledgeSource, KnowledgeSourceCreate, SitePage } from "@/lib/api/types";
import {
  aiSettings,
  billingState,
  json,
  knowledgeSource,
  noContent,
  planList,
  renderWithApi,
  sitePage,
  siteSource,
} from "@/test/api";

import { KnowledgePage } from "./KnowledgePage";
import { crawlSummary, pagePath } from "./SitePages";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

type State = { sources: KnowledgeSource[]; pages: SitePage[]; total?: number };

const PAGES: SitePage[] = [
  sitePage({ id: "p1", url: "https://maple.example/", title: "Maple Bakery" }),
  sitePage({ id: "p2", url: "https://maple.example/shipping", title: "Shipping policy" }),
  sitePage({
    id: "p3",
    url: "https://maple.example/returns",
    title: null,
    status: "failed",
    error: "The page returned an error (503).",
    ingest_status: null,
    last_crawled_at: null,
  }),
  sitePage({ id: "p4", url: "https://maple.example/blog", title: "Blog", status: "excluded", ingest_status: null }),
  sitePage({ id: "p5", url: "https://maple.example/old", title: "Old", status: "gone", error: "Not found (404).", ingest_status: null }),
  sitePage({ id: "p6", url: "https://maple.example/new", title: "New", ingest_status: "processing" }),
];

function setup(partial: Partial<State> = {}) {
  const state: State = { sources: [siteSource(), knowledgeSource()], pages: PAGES, ...partial };
  const view = renderWithApi(<KnowledgePage />, {
    handlers: {
      "GET /v1/w/:wid/ai-settings": () => json(aiSettings()),
      "GET /v1/w/:wid/knowledge-sources": () =>
        json({ items: state.sources, usage: { characters_used: 6_640, characters_limit: 200_000 } }),
      "POST /v1/w/:wid/knowledge-sources": (call) => {
        const body = call.body as KnowledgeSourceCreate;
        const created = siteSource(
          { status: "queued", pages_found: 0, pages_done: 0, recrawl: body.recrawl ?? "weekly", next_crawl_at: null, finished_at: null },
          { id: "site-new", title: body.title ?? "maple.example", url: body.url ?? null, status: "pending" },
        );
        state.sources = [created, ...state.sources];
        return json(created, 201);
      },
      "PATCH /v1/w/:wid/knowledge-sources/:id": (call, p) => {
        const patch = call.body as { excluded_paths?: string[]; recrawl?: "weekly" | "off" };
        const current = state.sources.find((s) => s.id === p.id)!;
        const updated = siteSource(
          { ...current.site!, ...(patch.excluded_paths ? { excluded_paths: patch.excluded_paths } : {}), ...(patch.recrawl ? { recrawl: patch.recrawl } : {}) },
          { id: current.id },
        );
        state.sources = state.sources.map((s) => (s.id === p.id ? updated : s));
        return json(updated);
      },
      "DELETE /v1/w/:wid/knowledge-sources/:id": (_, p) => {
        state.sources = state.sources.filter((s) => s.id !== p.id);
        return noContent();
      },
      "GET /v1/w/:wid/knowledge-sources/:id/pages": () =>
        json({ items: state.pages, total: state.total ?? state.pages.length }),
      "DELETE /v1/w/:wid/knowledge-sources/:id/pages/:pageId": (_, p) => {
        state.pages = state.pages.map((page) => (page.id === p.pageId ? { ...page, status: "removed" as const, ingest_status: null } : page));
        return noContent();
      },
      "POST /v1/w/:wid/knowledge-sources/:id/excluded-paths": (call, p) => {
        const { path } = call.body as { path: string };
        const current = state.sources.find((s) => s.id === p.id)!;
        const updated = siteSource({ ...current.site!, excluded_paths: [...current.site!.excluded_paths, path] }, { id: current.id });
        state.sources = state.sources.map((s) => (s.id === p.id ? updated : s));
        return json(updated);
      },
      "POST /v1/w/:wid/knowledge-sources/:id/recrawl": (_, p) => {
        const current = state.sources.find((s) => s.id === p.id)!;
        const updated = siteSource({ ...current.site!, status: "queued" }, { id: current.id, status: "pending", version: 2 });
        state.sources = state.sources.map((s) => (s.id === p.id ? updated : s));
        return json(updated);
      },
      "GET /v1/w/:wid/knowledge-gaps": () => json({ items: [] }),
      "GET /v1/w/:wid/billing": () => json(billingState()),
      "GET /v1/billing/plans": () => json(planList()),
    },
    upgradeDialog: true,
  });
  return { ...view, state };
}

async function openPages() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Show pages of maple.example" }));
  const panel = await screen.findByTestId("site-pages-site1");
  await within(panel).findByText("Shipping policy");
  return { user, panel };
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Website sources in the list (GR-35)", () => {
  it("shows the site with its address, page count and counts, and the other sources beside it", async () => {
    setup({ sources: [siteSource({ pages_found: 12, pages_done: 10, pages_failed: 2 }), knowledgeSource()] });
    const row = (await screen.findByText("maple.example")).closest("tr")!;
    expect(within(row).getByText("https://maple.example/")).toBeInTheDocument();
    expect(within(row).getByText("12 pages, 2 failed")).toBeInTheDocument();
    expect(within(row).getByText("5,400")).toBeInTheDocument(); // the pages' characters, not the site's 0
    expect(within(row).getByText("9 chunks")).toBeInTheDocument();
    expect(within(row).getAllByText("Ready").length).toBeGreaterThan(0);
    expect(screen.getByText("Do you ship to Dubai?")).toBeInTheDocument();
  });

  it("a site being read shows Processing, and its pages stay closed until opened", async () => {
    setup({ sources: [siteSource({ status: "running", pages_found: 4, pages_done: 1 }, { status: "processing" })] });
    const row = (await screen.findByText("maple.example")).closest("tr")!;
    expect(within(row).getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("site-pages-site1")).not.toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Show pages of maple.example" })).toHaveAttribute("aria-expanded", "false");
  });

  it("Add knowledge offers Website, which posts the address with the weekly check on by default", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ sources: [] });
    await user.click((await screen.findAllByRole("button", { name: "Add knowledge" }))[0]);
    await user.click(await screen.findByRole("menuitem", { name: "Website" }));
    const form = await screen.findByRole("form", { name: "Add a website" });
    const weekly = within(form).getByRole("checkbox", { name: "Check for changes every week" });
    expect(weekly).toBeChecked();
    await user.click(within(form).getByRole("button", { name: "Add" }));
    expect(await within(form).findByText("Enter a web address starting with http:// or https://.")).toBeInTheDocument();

    await user.type(within(form).getByLabelText("Website address"), "https://maple.example/");
    await user.click(weekly);
    await user.click(within(form).getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      type: "site",
      url: "https://maple.example/",
      title: null,
      recrawl: "off",
    });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Added to knowledge"));
  });

  it("editing a website shows its address, not an input, and sends only the changed setting", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Edit maple.example" }));
    const form = await screen.findByRole("form", { name: "Edit website" });
    expect(within(form).queryByLabelText("Website address")).not.toBeInTheDocument();
    expect(within(form).getByText("https://maple.example/")).toBeInTheDocument();
    await user.click(within(form).getByRole("checkbox", { name: "Check for changes every week" }));
    await user.click(within(form).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ reingest: false, recrawl: "off" });
  });

  it("deleting a website warns that its pages go too", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: "Delete maple.example" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/the site and all its pages/)).toBeInTheDocument();
  });
});

describe("A website's pages (GR-35)", () => {
  it("opens under the row with the summary, the next check and every page with its status", async () => {
    setup();
    const { panel } = await openPages();
    expect(within(panel).getByText("3 pages read.")).toBeInTheDocument();
    expect(within(panel).getByText(/Checked again .*Only pages that changed are read again/)).toBeInTheDocument();
    const items = within(panel).getAllByRole("listitem").filter((li) => li.hasAttribute("data-status"));
    expect(items).toHaveLength(6);
    const returns = items.find((li) => li.getAttribute("data-status") === "failed")!;
    expect(within(returns).getByText("/returns")).toBeInTheDocument(); // no title: the path
    expect(within(returns).getByText("The page returned an error (503).")).toBeInTheDocument();
    expect(within(returns).getByText("Failed")).toBeInTheDocument();
    expect(within(items[1]).getByText("Read")).toBeInTheDocument();
    expect(within(items[1]).getByText(/Read .* ago/)).toBeInTheDocument();
    expect(within(items.find((li) => li.getAttribute("data-status") === "gone")!).getByText("Gone")).toBeInTheDocument();
    expect(within(items.find((li) => li.getAttribute("data-status") === "excluded")!).getByText("Excluded")).toBeInTheDocument();
    expect(within(items[5]).getByText("Processing")).toBeInTheDocument(); // read, still being built
    // Closing hides them again.
    await userEvent.click(screen.getByRole("button", { name: "Hide pages of maple.example" }));
    expect(screen.queryByTestId("site-pages-site1")).not.toBeInTheDocument();
  });

  it("says when a crawl is running, stopped at the plan's cap, or failed", () => {
    const site = (over: Parameters<typeof siteSource>[0]) => siteSource(over).site!;
    expect(crawlSummary(site({ status: "running", pages_found: 4, pages_done: 1 }))).toBe("Reading the site: 4 pages found, 1 read.");
    expect(crawlSummary(site({ status: "queued" }))).toBe("Waiting to start reading the site.");
    expect(crawlSummary(site({ status: "failed", error: "robots.txt on this site doesn't let us read it." }))).toBe(
      "robots.txt on this site doesn't let us read it.",
    );
    expect(crawlSummary(site({ pages_done: 1, pages_failed: 0 }))).toBe("1 page read.");
    expect(crawlSummary(site({ pages_done: 24, pages_failed: 1 }))).toBe("24 pages read, 1 failed.");
    expect(pagePath("https://maple.example/blog/first")).toBe("/blog/first");
    expect(pagePath("not a url")).toBe("not a url");
  });

  it("tells when the plan's cap stopped the crawl", async () => {
    setup({ sources: [siteSource({ truncated: true, page_cap: 25, pages_found: 25, pages_done: 25 })] });
    const { panel } = await openPages();
    expect(within(panel).getByText("Stopped at 25 pages, the most your plan reads for one site.")).toBeInTheDocument();
  });

  it("with the weekly check off, the panel says it is not checked again by itself", async () => {
    setup({ sources: [siteSource({ recrawl: "off", next_crawl_at: null })] });
    const { panel } = await openPages();
    expect(within(panel).getByText("Not checked again by itself. Use Crawl now.")).toBeInTheDocument();
  });

  it("Crawl now asks for a new crawl and then shows it waiting", async () => {
    setup();
    const { user, panel } = await openPages();
    await user.click(within(panel).getByRole("button", { name: "Crawl now" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Reading the site again"));
    expect(await within(panel).findByText("Waiting to start reading the site.")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Crawling" })).toBeDisabled();
  });

  it("removing a page asks first, then calls the API and keeps the row as Removed", async () => {
    const { calls } = setup();
    const { user } = await openPages();
    await user.click(screen.getByRole("button", { name: "Actions for /shipping" }));
    await user.click(await screen.findByRole("menuitem", { name: "Remove page" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Remove /shipping?")).toBeInTheDocument();
    expect(within(dialog).getByText(/isn.t added back/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.path === "/v1/w/w1/knowledge-sources/site1/pages/p2")).toBe(true),
    );
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Removed /shipping"));
    const panel = screen.getByTestId("site-pages-site1");
    await waitFor(() => expect(within(panel).getByText("Removed")).toBeInTheDocument());
    expect(within(panel).queryByRole("button", { name: "Actions for /shipping" })).not.toBeInTheDocument();
  });

  it("excludes a path from a page's menu and from the box, and lists the excluded paths", async () => {
    const view = setup();
    const { user, panel } = await openPages();
    await user.click(screen.getByRole("button", { name: "Actions for /returns" }));
    await user.click(await screen.findByRole("menuitem", { name: "Exclude /returns" }));
    await waitFor(() =>
      expect(view.calls.find((c) => c.path.endsWith("/excluded-paths"))?.body).toEqual({ path: "/returns" }),
    );
    expect(await within(panel).findByText("/returns", { selector: "span" })).toBeInTheDocument();

    const input = within(panel).getByLabelText("Path to exclude");
    expect(within(panel).getByRole("button", { name: "Exclude" })).toBeDisabled();
    await user.type(input, "/blog");
    await user.click(within(panel).getByRole("button", { name: "Exclude" }));
    await waitFor(() => expect(view.calls.filter((c) => c.path.endsWith("/excluded-paths"))).toHaveLength(2));
    expect(view.calls.filter((c) => c.path.endsWith("/excluded-paths"))[1].body).toEqual({ path: "/blog" });
    expect(input).toHaveValue("");
  });

  it("taking a path off the list sends the remaining ones", async () => {
    const view = setup({ sources: [siteSource({ excluded_paths: ["/blog", "/old"] })] });
    const { user, panel } = await openPages();
    await user.click(within(panel).getByRole("button", { name: "Stop excluding /blog" }));
    await waitFor(() => expect(view.calls.find((c) => c.method === "PATCH")?.body).toEqual({ reingest: false, excluded_paths: ["/old"] }));
  });

  it("says when more pages exist than are shown, and when there are none", async () => {
    setup({ pages: PAGES, total: 450 });
    const { panel } = await openPages();
    expect(within(panel).getByText("Showing the first 6 of 450 pages.")).toBeInTheDocument();
  });

  it("an empty crawl says so", async () => {
    setup({ pages: [], sources: [siteSource({ status: "done", pages_found: 0, pages_done: 0 })] });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Show pages of maple.example" }));
    expect(await screen.findByText("No pages.")).toBeInTheDocument();
  });
});
