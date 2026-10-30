import { ArrowRight, Clock, Crown, Hourglass, type LucideIcon } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";

import { Ico } from "../landing/Ico";
import { BENTO, CELL_STATUS_LABEL, type Cell, type CellStatus } from "./content";
import { CellVisual } from "./visuals";

const STATUS: Record<CellStatus, { icon: LucideIcon; tone: string }> = {
  approval: { icon: Hourglass, tone: "t-need" },
  soon: { icon: Clock, tone: "t-plain" },
  pro: { icon: Crown, tone: "t-plain" },
};

/** A cell's status as a chip with its icon (StatusChip's look; "Pro" is a plan, not a status there). */
export function CellChip({ status }: { status: CellStatus }) {
  const { icon: Icon, tone } = STATUS[status];
  return (
    <span className={`tag chip ${tone}`} data-status={status}>
      <Icon size={13} strokeWidth={2.25} aria-hidden focusable="false" />
      {CELL_STATUS_LABEL[status]}
    </span>
  );
}

function CellLink({ cell }: { cell: Cell }) {
  const children = (
    <>
      {cell.title}
      <ArrowRight className="bx-arrow size-4" aria-hidden />
    </>
  );
  // An in-page link is a plain anchor; a page is a Next link.
  return cell.href.startsWith("#") ? (
    <a href={cell.href} className="bx-link">
      {children}
    </a>
  ) : (
    <Link href={cell.href as Route} className="bx-link">
      {children}
    </Link>
  );
}

/**
 * The /features bento grid (C-160): twelve columns on a wide screen. The two headline cells are tall
 * and wide with a product scene, two large cells hold a smaller scene, three medium cells a hint of
 * one, and the rest are small. Each cell is one link (its title's ::after covers it). The cells rise
 * in with a short stagger along each row (site.css), and the scenes play once as they arrive.
 */
export function BentoGrid() {
  return (
    <section className="xp-bento-band" aria-labelledby="bento-title">
      <div className="wrap">
        <h2 id="bento-title" className="sr-only">
          All features
        </h2>
        <ul className="bento">
          {BENTO.map((cell, index) => (
            <li
              key={cell.id}
              id={`f-${cell.id}`}
              className={`bx bx-${cell.size}${cell.ai ? " is-ai" : ""}`}
              data-rise=""
              style={{ "--n": index % 4 } as CSSProperties}
            >
              <div className="bx-top">
                {cell.platform ? (
                  <Ico className="ico-mark" style={{ "--c": `var(--${cell.platform === "facebook" ? "fb" : "web"})` } as CSSProperties}>
                    <PlatformGlyph platform={cell.platform} />
                  </Ico>
                ) : (
                  <Ico icon={cell.icon} className={cell.ai ? "ico-ai" : undefined} />
                )}
                {cell.status ? <CellChip status={cell.status} /> : null}
              </div>
              <h3 className="bx-t">
                <CellLink cell={cell} />
              </h3>
              <p className="bx-b">{cell.body}</p>
              {cell.visual ? (
                <div className="bx-vis">
                  <CellVisual visual={cell.visual} />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
