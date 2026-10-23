import Link from "next/link";
import { useId } from "react";

import { PostThumb } from "@/components/comments/PostThumb";
import { Card, CardBleed, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { refPath, workspaceHref } from "@/lib/agent/routes";
import { formatValue, httpsOnly } from "@/lib/agent/visuals";
import type { RankedPostsVisual } from "@/lib/api/types";
import { formatCount } from "@/lib/comments/format";

/**
 * GR-38: posts ranked by one metric, best first (top_posts), at most 10. A row is a link to the
 * post; the thumbnail is the platform's picture (a placeholder when there is none or it fails) and
 * the caption is the customer's own text, drawn as text and cut to one line. The figures sit in a
 * right-aligned column. The table scrolls inside the card, never the page (320 px).
 */
export function RankedPosts({
  visual,
  slug,
  onNavigate,
}: {
  visual: RankedPostsVisual;
  slug: string;
  onNavigate?: () => void;
}) {
  const titleId = useId();
  const details = [
    visual.period ? `Posts published ${visual.period.label}` : null,
    visual.age_label,
    `${formatCount(visual.considered)} ${visual.considered === 1 ? "post" : "posts"} compared`,
  ].filter(Boolean);

  return (
    <Card asChild padding="standard" className="space-y-3">
      <section aria-labelledby={titleId} data-testid="visual-ranked-posts">
        <CardHeader>
          <CardTitle id={titleId} className="text-sm">
            {visual.title}
          </CardTitle>
          <CardDescription>{details.join(" · ")}</CardDescription>
        </CardHeader>
        {visual.items.length === 0 ? (
          <p className="text-sm text-fg-secondary">Not enough posts to rank yet.</p>
        ) : (
          <CardBleed>
            <Table scrollLabel={`${visual.title}, scrolls sideways`}>
              <TableCaption className="sr-only">{visual.title}, best first</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">#</TableHead>
                  <TableHead>Post</TableHead>
                  <TableHead className="text-right">{visual.metric_label}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visual.items.map((item, index) => (
                  <TableRow key={item.post_id} data-testid="ranked-post">
                    <TableCell className="text-fg-secondary tabular-nums">{index + 1}</TableCell>
                    <TableCell className="min-w-40">
                      <Link
                        href={workspaceHref(slug, refPath({ kind: "post", id: item.post_id, label: item.label }))}
                        onClick={onNavigate}
                        className="flex items-center gap-3 rounded-md"
                      >
                        <PostThumb
                          post={{ thumbnail_url: httpsOnly(item.thumbnail_url), media_url: null, media_type: item.format }}
                          className="size-12 shrink-0 rounded-md"
                        />
                        <span className="min-w-0 space-y-0.5">
                          <span className="block text-sm font-medium">{item.label}</span>
                          {item.caption ? (
                            <span className="block max-w-56 truncate text-xs text-fg-secondary">{item.caption}</span>
                          ) : null}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">
                      {formatValue(visual.format, item.value)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardBleed>
        )}
      </section>
    </Card>
  );
}
