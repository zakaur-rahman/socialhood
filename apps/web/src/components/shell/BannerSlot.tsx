import Link from "next/link";
import type { Route } from "next";

import { cn } from "@/lib/utils";

export type Banner = {
  id: string;
  tone: "warning" | "danger";
  message: string;
  action?: { label: string; href: Route };
};

/**
 * UX-SH-04: app-level banners above page content (account needs reconnecting, payment on hold,
 * AI credits exhausted). One action each; critical states cannot be dismissed. Producers arrive
 * with the features that raise them (P2 reconnect, P5 credits, P8 billing).
 */
export function BannerSlot({ banners }: { banners: Banner[] }) {
  if (banners.length === 0) return null;
  return (
    <div className="space-y-2 px-4 pt-4 md:px-6" role="status">
      {banners.map((banner) => (
        <div
          key={banner.id}
          className={cn(
            "flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm",
            banner.tone === "danger" ? "bg-danger/15 text-danger-fg" : "bg-warning/15 text-warning",
          )}
        >
          <p className="flex-1">{banner.message}</p>
          {banner.action ? (
            <Link
              href={banner.action.href}
              className="shrink-0 rounded-md bg-white/10 px-3 py-1 font-medium text-fg hover:bg-white/15"
            >
              {banner.action.label}
            </Link>
          ) : null}
        </div>
      ))}
    </div>
  );
}
