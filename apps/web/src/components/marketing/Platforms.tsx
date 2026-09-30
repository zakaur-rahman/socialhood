import { MessageCircle } from "lucide-react";
import type { ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { cn } from "@/lib/utils";

import { Container, SectionHeading } from "./primitives";

type PlatformCard = {
  name: string;
  status: "available" | "later";
  mark: ReactNode;
  tile: string;
  body: string;
  points: string[];
};

const PLATFORMS: PlatformCard[] = [
  {
    name: "Instagram",
    status: "available",
    mark: <PlatformGlyph platform="instagram" className="size-5 text-white" />,
    tile: "bg-instagram",
    body: "Professional accounts (Business or Creator), connected with Instagram's own login.",
    points: ["DMs, comments, publishing and insights", "Personal accounts can switch to professional for free in the Instagram app"],
  },
  {
    name: "WhatsApp",
    status: "available",
    mark: <PlatformGlyph platform="whatsapp" className="size-5 text-white" />,
    tile: "bg-whatsapp",
    body: "WhatsApp Business numbers your business owns, connected through Meta's official Embedded Signup.",
    points: ["Chats in the same inbox as Instagram", "Meta bills WhatsApp messaging fees directly to your business"],
  },
  {
    name: "Facebook Messenger",
    status: "later",
    mark: <MessageCircle className="size-5 text-white" aria-hidden />,
    tile: "bg-facebook",
    body: "Messenger isn't supported yet.",
    points: [],
  },
];

export function Platforms() {
  return (
    <section aria-labelledby="platforms-title" className="border-t border-line-subtle py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="platforms-title"
          eyebrow="Platforms"
          title="Built on Meta's official APIs"
          intro="Social Hood connects only through Meta's official APIs for Instagram and WhatsApp."
        />
        <ul className="mt-14 grid gap-4 md:grid-cols-3">
          {PLATFORMS.map((platform) => (
            <li
              key={platform.name}
              className={cn(
                "flex flex-col rounded-2xl border border-line bg-panel p-6",
                platform.status === "later" && "border-dashed bg-panel/50",
              )}
            >
              <div className="flex items-center gap-3">
                <span className={cn("grid size-10 place-items-center rounded-xl", platform.tile, platform.status === "later" && "opacity-60")}>
                  {platform.mark}
                </span>
                <h3 className="text-base font-semibold">{platform.name}</h3>
                <span
                  className={cn(
                    "ml-auto rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
                    platform.status === "available" ? "bg-success/15 text-success" : "bg-raised text-fg-secondary",
                  )}
                >
                  {platform.status === "available" ? "Available" : "Coming later"}
                </span>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-fg-secondary">{platform.body}</p>
              {platform.points.length ? (
                <ul className="mt-4 space-y-2 text-sm">
                  {platform.points.map((point) => (
                    <li key={point} className="flex gap-2">
                      <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
