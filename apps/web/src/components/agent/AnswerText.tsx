"use client";

import Link from "next/link";
import { Fragment, useMemo, type ReactNode } from "react";

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
};

/** "Source 2: Post, Reel of 26 Sep" */
export function citationName(n: number, source: AnswerRef): string {
  return `Source ${n}: ${REF_KIND_LABEL[source.kind]}, ${source.label}`;
}

const CHIP =
  "inline-flex min-w-5 items-center justify-center rounded bg-brand-soft px-1 text-[11px] font-semibold leading-4 text-brand-fg tabular-nums";

/**
 * An answer in the markdown subset (FR-AGT-01, FR-AGT-04): paragraphs, bold, lists and small
 * tables of figures, with [n] citations linking to the post, conversation or other record used.
 * Built only from React elements; nothing in the answer is read as HTML.
 */
export function AnswerText({ answer, refs, slug, onNavigate }: Props) {
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
      const source = refs[inline.n - 1];
      return (
        <Link
          key={index}
          href={workspaceHref(slug, refPath(source))}
          onClick={onNavigate}
          aria-label={citationName(inline.n, source)}
          title={`${REF_KIND_LABEL[source.kind]}: ${source.label}`}
          className={cn(CHIP, "mx-0.5 align-baseline hover:bg-brand-line")}
          data-testid="citation"
        >
          {inline.n}
        </Link>
      );
    });

  return (
    <div className="space-y-3 text-sm leading-relaxed break-words text-fg" data-testid="answer">
      {blocks.map((block, index) => (
        <AnswerBlock key={index} block={block} inlines={inlines} />
      ))}
    </div>
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
      <li key={index} className="pl-1">
        {inlines(item)}
      </li>
    ));
    return block.ordered ? (
      <ol start={block.start} className="list-decimal space-y-1 pl-5 marker:text-fg-secondary">
        {items}
      </ol>
    ) : (
      <ul className="list-disc space-y-1 pl-5 marker:text-fg-secondary">{items}</ul>
    );
  }
  const alignClass = (column: number) =>
    block.align[column] === "right" ? "text-right" : block.align[column] === "center" ? "text-center" : "text-left";
  return (
    // Wide tables scroll inside the answer, never the page (375 px).
    <div className="max-w-full overflow-x-auto rounded-lg border border-line" role="region" aria-label="Table" tabIndex={0}>
      <table className="w-full border-collapse text-xs">
        <thead className="bg-white/5">
          <tr>
            {block.header.map((cell, column) => (
              <th
                key={column}
                scope="col"
                className={cn("px-3 py-2 font-semibold whitespace-nowrap text-fg-secondary", alignClass(column))}
              >
                {inlines(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-line-subtle">
              {row.map((cell, column) => (
                <td key={column} className={cn("px-3 py-2 tabular-nums", alignClass(column))}>
                  {inlines(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The records the answer used, numbered as its citations, each a link (40 px targets on phones). */
export function SourcesList({ refs, slug, onNavigate }: { refs: AnswerRef[]; slug: string; onNavigate?: () => void }) {
  if (refs.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase">Sources</p>
      <ol className="space-y-0.5" aria-label="Sources">
        {refs.map((source, index) => (
          <li key={`${source.kind}:${source.id}:${index}`}>
            <Link
              href={workspaceHref(slug, refPath(source))}
              onClick={onNavigate}
              className="-mx-2 flex min-h-10 items-center gap-2 rounded-md px-2 text-sm hover:bg-white/5 md:min-h-8"
            >
              <span className={CHIP} aria-hidden>
                {index + 1}
              </span>
              <span className="shrink-0 text-xs text-fg-secondary">{REF_KIND_LABEL[source.kind]}</span>
              <span className="min-w-0 truncate">{source.label}</span>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
