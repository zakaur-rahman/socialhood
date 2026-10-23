"use client";

import { MoreVertical, Plus, RefreshCw, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useExcludeSitePath, useRecrawlSite, useRemoveSitePage, useSitePages, useUpdateKnowledgeSource } from "@/lib/api/queries";
import type { KnowledgeSource, SiteCrawlInfo, SitePage, SitePageStatus } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const count = new Intl.NumberFormat("en-US");

/** A page's path, for a short label: "/blog/first" (the address when it can't be read). */
export function pagePath(url: string): string {
  try {
    const { pathname } = new URL(url);
    return pathname || "/";
  } catch {
    return url;
  }
}

const PAGE_STATUS: Record<SitePageStatus, { label: string; tone: "neutral" | "success" | "warning" | "danger" | "brand" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  done: { label: "Read", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  skipped: { label: "Skipped", tone: "neutral" },
  gone: { label: "Gone", tone: "warning" },
  excluded: { label: "Excluded", tone: "neutral" },
  removed: { label: "Removed", tone: "neutral" },
};

function PageStatusChip({ page }: { page: SitePage }) {
  // Read, but its text is still being turned into knowledge.
  if (page.status === "done" && (page.ingest_status === "pending" || page.ingest_status === "processing")) {
    return (
      <Badge tone="brand" size="md">
        <Spinner size="xs" /> Processing
      </Badge>
    );
  }
  const { label, tone } = PAGE_STATUS[page.status];
  return (
    <Badge tone={tone} size="md">
      {label}
    </Badge>
  );
}

/** Where the crawl is, in plain words (the line under the site's name). */
export function crawlSummary(info: SiteCrawlInfo): string {
  const pages = (n: number) => `${count.format(n)} ${n === 1 ? "page" : "pages"}`;
  if (info.status === "queued") return "Waiting to start reading the site.";
  if (info.status === "running") {
    return `Reading the site: ${pages(info.pages_found)} found, ${count.format(info.pages_done)} read.`;
  }
  if (info.status === "failed") return info.error ?? "Couldn't read this site.";
  if (info.status === "idle") return "Not read yet.";
  const failed = info.pages_failed > 0 ? `, ${count.format(info.pages_failed)} failed` : "";
  return `${pages(info.pages_done)} read${failed}.`;
}

/**
 * GR-35: a website source's pages. A summary of the crawl with Crawl now, the excluded paths, and
 * every address the crawl found with its status; a page can be removed (it isn't added back) and
 * a path excluded. Stacked rows, not a table, so it reads at 375 px.
 */
export function SitePages({ site, now }: { site: KnowledgeSource; now: Date }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const info = site.site;
  const crawling = info?.status === "queued" || info?.status === "running";
  const pages = useSitePages(wid, site.id, true, crawling);
  const recrawl = useRecrawlSite(wid);
  const update = useUpdateKnowledgeSource(wid);
  const exclude = useExcludeSitePath(wid);
  const remove = useRemoveSitePage(wid);
  const [removing, setRemoving] = useState<SitePage | null>(null);
  const [path, setPath] = useState("");
  const returnFocus = useReturnFocus();

  if (!info) return null;

  const crawlNow = () =>
    recrawl.mutate(site.id, {
      onSuccess: () => toast.success("Reading the site again"),
      onError: (error) => toastError(error),
    });

  const excludePath = (value: string) =>
    exclude.mutate(
      { siteId: site.id, path: value },
      {
        onSuccess: () => {
          setPath("");
          toast.success("Excluded. Its pages are removed and won't be read again.");
        },
        onError: (error) => toastError(error),
      },
    );

  const submitPath = (event: FormEvent) => {
    event.preventDefault();
    if (path.trim()) excludePath(path.trim());
  };

  const stopExcluding = (value: string) =>
    update.mutate(
      { id: site.id, patch: { excluded_paths: info.excluded_paths.filter((item) => item !== value) } },
      {
        onSuccess: () => toast.success("Back in. The next crawl reads it."),
        onError: (error) => toastError(error),
      },
    );

  const items = pages.data?.items ?? [];
  const total = pages.data?.total ?? 0;

  return (
    <div className="space-y-4 px-4 py-4 sm:px-5" data-testid={`site-pages-${site.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p role="status" className="text-sm">
            {crawlSummary(info)}
          </p>
          {info.truncated ? (
            <p className="text-xs text-fg-secondary">
              Stopped at {count.format(info.page_cap)} pages, the most your plan reads for one site.
            </p>
          ) : null}
          <p className="text-xs text-fg-secondary">
            {info.recrawl === "weekly"
              ? info.next_crawl_at && !crawling
                ? `Checked again ${new Date(info.next_crawl_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}. Only pages that changed are read again.`
                : "Checked again every week. Only pages that changed are read again."
              : "Not checked again by itself. Use Crawl now."}
          </p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={crawlNow} disabled={crawling || recrawl.isPending}>
          {crawling ? <Spinner size="xs" /> : <RefreshCw aria-hidden />} {crawling ? "Crawling" : "Crawl now"}
        </Button>
      </div>

      <section aria-label="Excluded paths" className="space-y-2">
        <h4 className="text-xs font-medium text-fg-secondary">Excluded paths</h4>
        {info.excluded_paths.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {info.excluded_paths.map((value) => (
              <li key={value}>
                <Badge tone="neutral" size="md" className="gap-1 pr-1">
                  {value}
                  <button
                    type="button"
                    className="grid size-4 place-items-center rounded-full hover:bg-hover pointer-coarse:size-6"
                    aria-label={`Stop excluding ${value}`}
                    onClick={() => stopExcluding(value)}
                  >
                    <X aria-hidden />
                  </button>
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
        <form onSubmit={submitPath} className="flex gap-2">
          <Input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="/blog"
            maxLength={200}
            aria-label="Path to exclude"
            className="min-w-0 flex-1"
          />
          <Button type="submit" variant="secondary" size="sm" disabled={!path.trim() || exclude.isPending}>
            <Plus aria-hidden /> Exclude
          </Button>
        </form>
      </section>

      <section aria-label="Pages" className="space-y-2">
        <h4 className="text-xs font-medium text-fg-secondary">Pages</h4>
        {pages.isPending ? (
          <p className="text-sm text-fg-secondary" role="status">
            Loading pages
          </p>
        ) : pages.isError ? (
          <p className="text-sm text-danger-fg" role="alert">
            Couldn&apos;t load the pages.{" "}
            <button type="button" className="underline" onClick={() => void pages.refetch()}>
              Try again
            </button>
          </p>
        ) : items.length === 0 ? (
          <p className="text-sm text-fg-secondary">{crawling ? "No pages found yet." : "No pages."}</p>
        ) : (
          <ul className="divide-y divide-line rounded-lg border border-line">
            {items.map((page) => {
              const label = pagePath(page.url);
              const active = page.status !== "removed" && page.status !== "excluded";
              return (
                <li key={page.id} className="flex items-start gap-2 p-3" data-status={page.status}>
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="truncate text-sm font-medium" title={page.url}>
                      {page.title ?? label}
                    </p>
                    <p className="truncate text-xs text-fg-secondary" title={page.url}>
                      {label}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <PageStatusChip page={page} />
                      {page.last_crawled_at ? (
                        <span className="text-xs text-fg-secondary">Read {relativeTime(page.last_crawled_at, now)} ago</span>
                      ) : null}
                    </div>
                    {page.error && (page.status === "failed" || page.status === "skipped" || page.status === "gone") ? (
                      <p className={page.status === "failed" ? "text-xs text-danger-fg" : "text-xs text-fg-secondary"}>{page.error}</p>
                    ) : null}
                  </div>
                  {active ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`Actions for ${label}`}>
                          <MoreVertical aria-hidden />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setRemoving(page)}>Remove page</DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => excludePath(label)} disabled={label === "/"}>
                          Exclude {label}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
        {total > items.length ? (
          <p className="text-xs text-fg-secondary">
            Showing the first {count.format(items.length)} of {count.format(total)} pages.
          </p>
        ) : null}
      </section>

      <AlertDialog open={Boolean(removing)} onOpenChange={(open) => (open ? undefined : setRemoving(null))}>
        <AlertDialogContent {...returnFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing ? pagePath(removing.url) : "this page"}?</AlertDialogTitle>
            <AlertDialogDescription>
              The AI stops using this page right away. It isn&apos;t added back when the site is read again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const page = removing;
                if (!page) return;
                remove.mutate(
                  { siteId: site.id, pageId: page.id },
                  {
                    onSuccess: () => toast.success(`Removed ${pagePath(page.url)}`),
                    onError: (error) => toastError(error),
                  },
                );
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
