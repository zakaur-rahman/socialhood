"use client";

import Link from "next/link";
import { Fragment, useMemo, type ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { parseAnswer, type Block, type Inline } from "@/lib/agent/answer";
import { REF_KIND_LABEL } from "@/lib/agent/format";
import { refPath, workspaceHref } from "@/lib/agent/routes";
import type { AnswerRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Props = {
  answer: string;
  refs: AnswerRef[];
  slug: string;
  /** Following a citation leaves the panel: the caller closes it. */
  onNavigate?: () => void;
  className?: string;
};

/** "Source 2: Post, Reel of 26 Sep" */
export function citationName(n: number, source: AnswerRef): string {
  return `Source ${n}: ${REF_KIND_LABEL[source.kind]}, ${source.label}`;
}

/**
 * An answer in the markdown subset (FR-AGT-01, FR-AGT-04): paragraphs, bold, lists and small
 * tables of figures, set for reading (`text-md`: 15 px on 24 px lines), with [n] citations as
 * small pills that name their record on hover or focus and link to it. Built only from React
 * elements; nothing in the answer is read as HTML.
 */
export function AnswerText({ answer, refs, slug, onNavigate, className }: Props) {
  const blocks = useMemo(() => parseAnswer(answer, refs.length), [answer, refs.length]);

  const inlines = (items: Inline[]): ReactNode[] =>
    items.map((inline, index) => {
      if (inline.type === "text") return <Fragment key={index}>{inline.text}</Fragment>;
      if (inline.type === "bold") {
        return (
          <strong key={index} className="font-semibold text-fg">
            {inlines(inline.children)}
          </strong>
        );
      }
      return <Citation key={index} n={inline.n} source={refs[inline.n - 1]} slug={slug} onNavigate={onNavigate} />;
    });

  return (
    <div
      className={cn("space-y-4 text-md break-words text-fg", className)}
      data-testid="answer"
    >
      {blocks.map((block, index) => (
        <AnswerBlock key={index} block={block} inlines={inlines} />
      ))}
    </div>
  );
}

function Citation({
  n,
  source,
  slug,
  onNavigate,
}: {
  n: number;
  source: AnswerRef;
  slug: string;
  onNavigate?: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          href={workspaceHref(slug, refPath(source))}
          onClick={onNavigate}
          aria-label={citationName(n, source)}
          className="relative -top-px mx-0.5 inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-raised px-1 align-middle text-2xs leading-none font-medium text-fg-secondary tabular-nums no-underline hover:bg-brand-soft hover:text-brand-fg focus-visible:bg-brand-soft focus-visible:text-brand-fg"
          data-testid="citation"
        >
          {n}
        </Link>
      </TooltipTrigger>
      <TooltipContent side="top">
        {REF_KIND_LABEL[source.kind]} · {source.label}
      </TooltipContent>
    </Tooltip>
  );
}

function AnswerBlock({ block, inlines }: { block: Block; inlines: (items: Inline[]) => ReactNode[] }) {
  if (block.type === "paragraph") {
    return (
      <p>
        {block.lines.map((line, index) => (
          <Fragment key={index}>
            {index > 0 ? <br /> : null}
            {inlines(line)}
          </Fragment>
        ))}
      </p>
    );
  }
  if (block.type === "list") {
    const items = block.items.map((item, index) => (
      <li key={index} className="pl-1.5">
        {inlines(item)}
      </li>
    ));
    return block.ordered ? (
      <ol start={block.start} className="list-decimal space-y-1.5 pl-6 marker:text-fg-secondary">
        {items}
      </ol>
    ) : (
      <ul className="list-disc space-y-1.5 pl-6 marker:text-fg-secondary">{items}</ul>
    );
  }
  const alignClass = (column: number) =>
    block.align[column] === "right" ? "text-right" : block.align[column] === "center" ? "text-center" : "text-left";
  return (
    // A frame sets the table off from the text around it. Wide tables scroll inside the answer,
    // never the page (375 px), and the scroller can be reached by keyboard.
    <div className="rounded-lg border border-line">
      <Table scrollLabel="Table">
        <TableHeader>
          <TableRow>
            {block.header.map((cell, column) => (
              <TableHead key={column} className={alignClass(column)}>
                {inlines(cell)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {block.rows.map((row, rowIndex) => (
            <TableRow key={rowIndex}>
              {row.map((cell, column) => (
                <TableCell key={column} className={alignClass(column)}>
                  {inlines(cell)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** The records the answer used, numbered as its citations: a wrap of small chips, each a link. */
export function SourcesList({ refs, slug, onNavigate }: { refs: AnswerRef[]; slug: string; onNavigate?: () => void }) {
  if (refs.length === 0) return null;
  return (
    <ol className="flex flex-wrap gap-1.5" aria-label="Sources">
      {refs.map((source, index) => (
        <li key={`${source.kind}:${source.id}:${index}`} className="min-w-0 max-w-full">
          <Link
            href={workspaceHref(slug, refPath(source))}
            onClick={onNavigate}
            title={`${REF_KIND_LABEL[source.kind]}: ${source.label}`}
            className="inline-flex min-h-7 max-w-full items-center gap-1.5 rounded-full border border-line bg-hover px-2.5 text-xs text-fg-secondary hover:bg-pressed hover:text-fg motion-safe:transition-[color,background-color] pointer-coarse:min-h-10 pointer-coarse:px-3"
          >
            <span className="font-medium text-fg tabular-nums">{index + 1}</span>
            <span aria-hidden>·</span>
            <span className="min-w-0 truncate">
              <span className="sr-only">{REF_KIND_LABEL[source.kind]}: </span>
              {source.label}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
