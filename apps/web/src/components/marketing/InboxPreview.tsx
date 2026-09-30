import { Pencil, Send, Sparkles } from "lucide-react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { cn } from "@/lib/utils";

type Row = {
  name: string;
  preview: string;
  platform: "instagram" | "whatsapp";
  time: string;
  chip?: { label: string; tone: "brand" | "warning" | "success" };
  active?: boolean;
  unread?: boolean;
};

// Example people and messages only: this is a drawing of the inbox, not anyone's data.
const ROWS: Row[] = [
  { name: "Priya S.", preview: "Blue kurta M size mein available hai?", platform: "instagram", time: "2m", chip: { label: "Lead", tone: "success" }, active: true, unread: true },
  { name: "Rahul Mehta", preview: "The parcel hasn't arrived yet", platform: "whatsapp", time: "9m", chip: { label: "Needs you", tone: "warning" }, unread: true },
  { name: "Ananya", preview: "What are your shop timings on Sunday?", platform: "instagram", time: "24m" },
  { name: "Kabir Stores", preview: "Thank you, received!", platform: "whatsapp", time: "1h" },
];

const TONE = {
  brand: "bg-brand-soft text-brand-fg",
  warning: "bg-warning/15 text-warning",
  success: "bg-success/15 text-success",
} as const;

const PLATFORM_DOT = { instagram: "bg-instagram", whatsapp: "bg-whatsapp" } as const;

function Chip({ tone, children }: { tone: keyof typeof TONE; children: string }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap", TONE[tone])}>{children}</span>;
}

function Avatar({ name, platform, size = "size-9" }: { name: string; platform: Row["platform"]; size?: string }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2);
  return (
    <span className={cn("relative grid shrink-0 place-items-center rounded-full bg-raised text-xs font-semibold text-fg", size)}>
      {initials}
      <span className={cn("absolute -right-0.5 -bottom-0.5 grid size-4 place-items-center rounded-full ring-2 ring-panel", PLATFORM_DOT[platform])}>
        <PlatformGlyph platform={platform} className="size-2.5 text-white" />
      </span>
    </span>
  );
}

/**
 * An illustration of the inbox built from the app's tokens: a conversation list, a customer's
 * Hinglish question and an AI draft from the shop's knowledge. It is marked as an illustration and
 * shows no metrics. Screen readers get one description instead of the drawing.
 */
export function InboxPreview() {
  return (
    <figure className="relative">
      <div
        role="img"
        aria-label="Illustration of the Social Hood inbox: a customer asks on Instagram, in Hinglish, whether a kurta is available and what it costs, and an AI draft reply written from the shop's knowledge waits for the owner to send it."
        className="relative overflow-hidden rounded-2xl border border-line-strong bg-panel shadow-2xl shadow-brand/10"
      >
        <div className="flex h-10 items-center gap-2 border-b border-line px-4" aria-hidden>
          <span className="size-2.5 rounded-full bg-raised-hover" />
          <span className="size-2.5 rounded-full bg-raised-hover" />
          <span className="size-2.5 rounded-full bg-raised-hover" />
          <span className="ml-2 text-xs font-medium text-fg-secondary">Inbox</span>
          <span className="ml-auto rounded-full border border-line px-2 py-0.5 text-[10px] font-semibold tracking-wider text-fg-secondary uppercase">
            Illustration
          </span>
        </div>
        <div className="grid md:grid-cols-[15rem_1fr]" aria-hidden>
          <ul className="hidden border-r border-line md:block">
            {ROWS.map((row) => (
              <li
                key={row.name}
                className={cn("flex items-start gap-3 border-b border-line-subtle px-3 py-3", row.active && "bg-raised")}
              >
                <Avatar name={row.name} platform={row.platform} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className={cn("truncate text-sm", row.unread ? "font-semibold text-fg" : "text-fg")}>{row.name}</span>
                    <span className="ml-auto text-[11px] text-fg-secondary tabular-nums">{row.time}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-fg-secondary">{row.preview}</span>
                  {row.chip ? (
                    <span className="mt-1.5 flex">
                      <Chip tone={row.chip.tone}>{row.chip.label}</Chip>
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>

          <div className="flex min-w-0 flex-col bg-canvas">
            <div className="flex items-center gap-3 border-b border-line bg-panel px-4 py-2.5">
              <Avatar name="Priya S." platform="instagram" size="size-8" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">Priya S.</span>
                <span className="block truncate text-xs text-fg-secondary">@priya.styles · Instagram</span>
              </span>
              <span className="hidden gap-1.5 sm:flex">
                <Chip tone="brand">AI: Suggest</Chip>
                <span className="rounded-full bg-raised px-2 py-0.5 text-[11px] whitespace-nowrap text-fg-secondary">Window: 23h left</span>
              </span>
            </div>

            <div className="flex flex-1 flex-col gap-3 px-4 py-5">
              <div className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-brand-gradient px-3 py-2 text-sm text-white">
                Hi Priya! New colours just dropped this week.
              </div>
              <div className="max-w-[85%] self-start">
                <div className="rounded-2xl rounded-bl-md border border-line-subtle bg-field px-3 py-2 text-sm leading-relaxed">
                  Hi! Blue kurta M size mein available hai? Price kya hai?
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Chip tone="brand">Price question</Chip>
                  <Chip tone="success">Lead</Chip>
                </div>
              </div>
            </div>

            <div className="m-3 rounded-xl border border-brand-line bg-panel p-3">
              <div className="flex items-start gap-2">
                <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-fg" />
                <p className="min-w-0 flex-1 text-sm leading-relaxed">
                  <span className="font-medium text-brand-fg">AI draft: </span>
                  Haan, blue kurta M size mein available hai. Price ₹1,499 hai, aur delivery 3 se 5 din mein ho jaati hai.
                  Order karna hai?
                </p>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-5.5">
                <span className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-fg-secondary">Price list</span>
                <span className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-fg-secondary">Delivery FAQ</span>
                <span className="ml-auto flex gap-1.5">
                  <span className="inline-flex h-7 items-center gap-1 rounded-md bg-raised px-2.5 text-xs text-fg">
                    <Pencil className="size-3" /> Edit
                  </span>
                  <span className="bg-brand-gradient inline-flex h-7 items-center gap-1 rounded-md px-2.5 text-xs font-medium text-white">
                    <Send className="size-3" /> Send
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-fg-secondary">
        Illustration of the inbox. The people, messages and prices are examples.
      </figcaption>
    </figure>
  );
}
