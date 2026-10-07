import { MessageCircle } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { Container } from "./primitives";

type Platform = { name: string; status: "available" | "later"; mark: ReactNode; tile: string; body: string };

// The product guide's "Supported platforms". No customer logos: we show only what we connect to.
const PLATFORMS: Platform[] = [
  {
    name: "Instagram",
    status: "available",
    mark: <PlatformGlyph platform="instagram" className="size-5 text-on-brand" />,
    tile: "bg-instagram",
    body: "Professional accounts (Business or Creator), with Instagram's own login. DMs, comments, publishing and insights.",
  },
  {
    name: "WhatsApp",
    status: "available",
    mark: <PlatformGlyph platform="whatsapp" className="size-5 text-on-brand" />,
    tile: "bg-whatsapp",
    body: "WhatsApp Business numbers your business owns, through Meta's Embedded Signup. Meta bills its messaging fees to you directly.",
  },
  {
    name: "Facebook Messenger",
    status: "later",
    mark: <MessageCircle className="size-5 text-on-brand" aria-hidden />,
    tile: "bg-facebook",
    body: "Messenger isn't supported yet.",
  },
];

/** The strip under the hero: where Social Hood works, and that it connects only the official way. */
export function Platforms() {
  return (
    <section aria-labelledby="platforms-title" className="relative py-14 sm:py-16">
      <Container>
        <div className="flex flex-col items-center gap-2 text-center">
          <h2 id="platforms-title" className="text-xl font-semibold tracking-tight sm:text-2xl">
            Built on Meta&apos;s official APIs
          </h2>
          <p className="max-w-xl text-sm text-fg-secondary">
            Social Hood connects only through Meta&apos;s official APIs for Instagram and WhatsApp, and never asks for your password.
          </p>
        </div>
        <ul className="mx-auto mt-8 grid max-w-5xl gap-3 md:grid-cols-3">
          {PLATFORMS.map((platform, index) => (
            <li key={platform.name} data-reveal style={{ "--reveal-delay": `${index * 80}ms` } as CSSProperties}>
              <div
                className={cn(
                  "flex h-full gap-4 rounded-2xl border p-4 transition-colors duration-slow",
                  platform.status === "available" ? "border-line bg-panel hover:border-line-strong" : "border-dashed border-line bg-panel/50",
                )}
              >
                <span className={cn("grid size-10 shrink-0 place-items-center rounded-xl", platform.tile, platform.status === "later" && "opacity-60")}>
                  {platform.mark}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <h3 className="text-sm font-semibold">{platform.name}</h3>
                    <Badge size="md" tone={platform.status === "available" ? "success" : "neutral"}>
                      {platform.status === "available" ? "Official API" : "Coming later"}
                    </Badge>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-fg-secondary">{platform.body}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
