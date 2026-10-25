import Link from "next/link";
import { useId } from "react";

import { Card, CardBleed, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { visualPath, workspaceHref } from "@/lib/agent/routes";
import { cellText, moreRows } from "@/lib/agent/tables";
import type { TableVisual } from "@/lib/api/types";
import { formatCount } from "@/lib/comments/format";
import { cn } from "@/lib/utils";

/**
 * VIS-09: a short table of what a tool listed (search_conversations, list_orders): at most 10 rows
 * and 6 columns. Figures sit in right-aligned columns with tabular digits; text cells may be the
 * customer's own words and are drawn as text, cut to one line. "+N more" links to the full page
 * when the API gave one. The table scrolls inside the card, never the page (375 px).
 */
export function DataTableVisual({ visual, slug, onNavigate }: { visual: TableVisual; slug: string; onNavigate?: () => void }) {
  const titleId = useId();
  const more = moreRows(visual);
  const morePath = visualPath(visual.more_route);

  return (
    <Card asChild padding="standard" className="space-y-3">
      <section aria-labelledby={titleId} data-testid="visual-table">
        <CardHeader>
          <CardTitle id={titleId} className="text-sm">
            {visual.title}
          </CardTitle>
          <CardDescription>
            {visual.total === 1 ? "1 row" : `${formatCount(visual.total)} rows`}
            {more > 0 ? `, ${formatCount(visual.rows.length)} shown` : ""}
          </CardDescription>
        </CardHeader>
        {visual.rows.length === 0 ? (
          <p className="text-sm text-fg-secondary">Nothing to show.</p>
        ) : (
          <CardBleed>
            <Table scrollLabel={`${visual.title}, scrolls sideways`}>
              <TableCaption className="sr-only">{visual.title}</TableCaption>
              <TableHeader>
                <TableRow>
                  {visual.columns.map((column) => (
                    <TableHead key={column.key} className={cn(column.align === "right" && "text-right")}>
                      {column.label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {visual.rows.map((row, index) => (
                  <TableRow key={index} data-testid="table-row">
                    {visual.columns.map((column, at) => (
                      <TableCell
                        key={column.key}
                        className={cn(column.align === "right" ? "text-right font-medium tabular-nums" : "max-w-48 truncate")}
                      >
                        {cellText(row.cells[at], column)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardBleed>
        )}
        {more > 0 ? (
          <p className="text-sm text-fg-secondary" data-testid="table-more">
            {morePath ? (
              <Link href={workspaceHref(slug, morePath)} onClick={onNavigate} className="text-brand-fg underline-offset-4 hover:underline">
                +{formatCount(more)} more
              </Link>
            ) : (
              <>+{formatCount(more)} more</>
            )}
          </p>
        ) : null}
      </section>
    </Card>
  );
}
