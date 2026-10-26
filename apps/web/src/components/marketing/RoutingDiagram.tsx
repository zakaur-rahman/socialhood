import { BarChart3, BookOpen, Hand, IndianRupee, Reply, ShoppingBag, Table2, type LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import type { Platform } from "@/lib/api/types";
import { SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { RoutingPulses } from "./effects/RoutingPulses";
import { LogoMark } from "./primitives";
import { LAYOUTS, percent, trackD, type OutcomeId, type Point, type RoutingLayout, type SourceId } from "./routing";

/**
 * Where a message comes from (C-141). Logos only for the platforms we ship as glyphs; Facebook
 * Pages carry "soon" until Meta's approval (C-138).
 */
export const ROUTING_SOURCES: Record<SourceId, { label: string; short: string; platform: Platform; tile: string; badge?: string; note?: string }> = {
  "ig-dm": { label: "Instagram DMs", short: "DMs", platform: "instagram", tile: "bg-instagram-logo-gradient", badge: "DM" },
  "ig-comment": { label: "Instagram comments", short: "Comments", platform: "instagram", tile: "bg-instagram-logo-gradient", badge: "Comment" },
  whatsapp: { label: "WhatsApp", short: "WhatsApp", platform: "whatsapp", tile: "bg-whatsapp-logo", badge: "Chat" },
  web: { label: "Website chat", short: "Website", platform: "web", tile: "bg-web", badge: "Widget" },
  facebook: { label: "Facebook Pages", short: "Facebook", platform: "facebook", tile: "bg-facebook-logo", note: "soon" },
};

/**
 * What comes out (C-141), each true today: the reply, the hand-off to Needs you, a Razorpay or UPI
 * link and Google Sheets (both Pro, C-103, C-120), and the Monday report (C-130).
 */
export const ROUTING_OUTCOMES: Record<OutcomeId, { label: string; short: string; icon: LucideIcon; tile: string; badge?: string; note?: string }> = {
  reply: { label: "Reply in the same chat", short: "Reply", icon: Reply, tile: "bg-success-soft text-success", badge: "Reply" },
  "needs-you": { label: "Needs you, for your team", short: "Needs you", icon: Hand, tile: "bg-warning-soft text-warning", badge: "Hand-off" },
  payment: { label: "Razorpay or UPI link", short: "Payment", icon: IndianRupee, tile: "bg-brand-soft text-brand-fg", note: "Pro" },
  sheets: { label: "Lead to Google Sheets", short: "Sheets", icon: Table2, tile: "bg-brand-soft text-brand-fg", badge: "Lead", note: "Pro" },
  report: { label: "Monday report", short: "Report", icon: BarChart3, tile: "bg-brand-soft text-brand-fg" },
};

const KNOWLEDGE = {
  knowledge: { label: "Your knowledge", short: "Knowledge", icon: BookOpen },
  catalogue: { label: "Your catalogue", short: "Catalogue", icon: ShoppingBag },
};

/** One sentence for screen readers; the drawing itself is decorative. */
export const ROUTING_SUMMARY = `Messages from Instagram DMs and comments, WhatsApp, your website chat and, soon, Facebook Pages come into ${SITE_NAME}, which answers from your own knowledge and catalogue, then replies in the same chat, hands the chat to your team, sends a payment link, adds a lead to Google Sheets or counts it in your Monday report.`;

/** A box positioned by its centre, in percent of the diagram, `size` units wide (and square). */
function at(layout: RoutingLayout, point: Point, size?: number): CSSProperties {
  return { ...percent(layout, point), ...(size ? { width: `${(size / layout.width) * 100}%` } : {}) };
}

function Node({
  layout,
  point,
  tile,
  label,
  badge,
  note,
  side,
  children,
  id,
}: {
  layout: RoutingLayout;
  point: Point;
  tile: string;
  label: string;
  badge?: string;
  note?: string;
  side: "source" | "outcome";
  children: ReactNode;
  id: string;
}) {
  const wide = layout.name === "wide";
  return (
    <div
      data-routing-node={id}
      data-side={side}
      className="absolute aspect-square -translate-x-1/2 -translate-y-1/2"
      style={at(layout, point, layout.tile)}
    >
      <div className="size-full rounded-2xl border border-line bg-panel p-[9%] shadow-glass">
        <div className={cn("grid size-full place-items-center rounded-xl", tile)}>{children}</div>
      </div>
      {wide && badge ? (
        <span className="absolute -top-2 left-3/4 rounded-full border border-line bg-canvas px-1.5 text-2xs whitespace-nowrap text-fg-secondary">
          {badge}
        </span>
      ) : null}
      <span
        className={cn(
          "absolute top-full left-1/2 mt-1.5 flex -translate-x-1/2 items-center gap-1 whitespace-nowrap text-fg-secondary",
          wide ? "text-xs" : "flex-col gap-0.5 text-2xs",
        )}
      >
        {label}
        {note ? <span className="rounded-full bg-hover px-1.5 text-2xs text-fg-secondary">{note}</span> : null}
      </span>
    </div>
  );
}

function Diagram({ layout }: { layout: RoutingLayout }) {
  const wide = layout.name === "wide";
  const { hub } = layout;
  const ports = [-1, -0.5, 0, 0.5, 1];
  return (
    <div
      data-routing-layout={layout.name}
      className="relative w-full select-none"
      style={{ aspectRatio: `${layout.width} / ${layout.height}` }}
    >
      {/* The tracks: hairlines from every source into the hub and out to every outcome, and the
          dotted ties to what the AI answers from. */}
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" fill="none">
        {layout.knowledge.map((k) => (
          <path key={k.id} data-routing-track={`knowledge-${k.id}`} d={trackD(k.path, layout.radius)} className="stroke-line-strong" strokeWidth={1} strokeDasharray="2 4" vectorEffect="non-scaling-stroke" />
        ))}
        {[...layout.sources, ...layout.outcomes].map((node) => (
          <path key={node.id} data-routing-track={node.id} d={trackD(node.path, layout.radius)} className="stroke-line-strong" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        ))}
      </svg>

      <RoutingPulses layout={layout.name} />

      {/* What the AI answers from, above the hub (beside it on phones). */}
      {wide ? (
        <p className="absolute -translate-x-1/2 -translate-y-1/2 text-2xs whitespace-nowrap text-fg-secondary" style={at(layout, [500, 46])}>
          Answers only from what you added
        </p>
      ) : null}
      {layout.knowledge.map((k) => {
        const { icon: Icon, label, short } = KNOWLEDGE[k.id];
        return (
          <span
            key={k.id}
            data-routing-node={k.id}
            className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-lg border border-dashed border-line-strong bg-panel px-2 py-1 text-xs whitespace-nowrap text-fg shadow-glass"
            style={at(layout, k.at)}
          >
            <Icon className="size-3.5 text-brand-fg" aria-hidden />
            {wide ? label : short}
          </span>
        );
      })}

      {/* The hub: the logo on a raised bezel, with the ports the tracks plug into. */}
      <div data-routing-node="hub" className="absolute aspect-square -translate-x-1/2 -translate-y-1/2" style={at(layout, hub.at, hub.size)}>
        <div aria-hidden className="bg-glow-brand-centre pointer-events-none absolute -inset-1/2 rounded-full" />
        {ports.map((p) =>
          wide ? (
            <span key={p} className="contents">
              <span className="absolute -left-1 h-1 w-1.5 -translate-y-1/2 rounded-full bg-line-control" style={{ top: `${50 + ((p * 28) / hub.size) * 100}%` }} />
              <span className="absolute -right-1 h-1 w-1.5 -translate-y-1/2 rounded-full bg-line-control" style={{ top: `${50 + ((p * 28) / hub.size) * 100}%` }} />
            </span>
          ) : (
            <span key={p} className="contents">
              <span className="absolute -top-1 h-1.5 w-1 -translate-x-1/2 rounded-full bg-line-control" style={{ left: `${50 + ((p * 24) / hub.size) * 100}%` }} />
              <span className="absolute -bottom-1 h-1.5 w-1 -translate-x-1/2 rounded-full bg-line-control" style={{ left: `${50 + ((p * 24) / hub.size) * 100}%` }} />
            </span>
          ),
        )}
        <div className="relative size-full rounded-3xl border border-line-strong bg-panel p-[8%] shadow-glow">
          <div className="size-full rounded-2xl border border-line p-[4%] shadow-highlight">
            <LogoMark className="size-full rounded-xl" />
          </div>
        </div>
        {wide ? (
          <span className="absolute top-full left-1/2 mt-2 -translate-x-1/2 text-xs font-medium whitespace-nowrap text-fg">{SITE_NAME} AI</span>
        ) : null}
      </div>

      {layout.sources.map((node) => {
        const meta = ROUTING_SOURCES[node.id];
        return (
          <Node key={node.id} id={node.id} side="source" layout={layout} point={node.at} tile={meta.tile} label={wide ? meta.label : meta.short} badge={meta.badge} note={meta.note}>
            <PlatformGlyph platform={meta.platform} className="size-1/2 text-on-brand" />
          </Node>
        );
      })}
      {layout.outcomes.map((node) => {
        const meta = ROUTING_OUTCOMES[node.id];
        const Icon = meta.icon;
        return (
          <Node key={node.id} id={node.id} side="outcome" layout={layout} point={node.at} tile={meta.tile} label={wide ? meta.label : meta.short} badge={meta.badge} note={meta.note}>
            <Icon className="size-1/2" aria-hidden />
          </Node>
        );
      })}

      {/* The micro-labels between the tracks. */}
      {wide ? (
        <>
          <p className="absolute -translate-y-1/2 text-xs leading-snug text-fg-secondary" style={at(layout, [345, 462])}>
            Every message
            <br />
            comes in
          </p>
          <p className="absolute -translate-x-full -translate-y-1/2 text-right text-xs leading-snug text-fg-secondary" style={at(layout, [655, 462])}>
            The right answer
            <br />
            goes out
          </p>
        </>
      ) : null}
    </div>
  );
}

/**
 * The hero's routing diagram (C-141): every channel into one hub and the right outcome out. The
 * nodes, tracks and labels are server-rendered and complete without JavaScript; only the pulses
 * and the example chips (RoutingPulses) move. Wide from `lg`, stacked below it.
 */
export function RoutingDiagram({ className }: { className?: string }) {
  return (
    <figure className={cn("relative", className)}>
      <figcaption className="sr-only">{ROUTING_SUMMARY}</figcaption>
      <div aria-hidden data-routing-diagram="">
        <div className="hidden lg:block">
          <Diagram layout={LAYOUTS.wide} />
        </div>
        <div className="mx-auto max-w-md lg:hidden">
          <Diagram layout={LAYOUTS.stack} />
        </div>
      </div>
    </figure>
  );
}
