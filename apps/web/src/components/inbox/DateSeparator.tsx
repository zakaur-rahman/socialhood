import { formatDay } from "@/lib/tz";

/** UX-INB-06: Today, Yesterday, "Mon 3 Mar", "3 Mar 2025", in the workspace timezone. */
export function DateSeparator({ at, timeZone, now }: { at: string; timeZone: string; now: Date }) {
  return (
    <div role="separator" className="flex justify-center py-2">
      <span className="text-xs text-fg-secondary">{formatDay(at, timeZone, now)}</span>
    </div>
  );
}

/** A centred note in the thread ("AI paused until 16:40 because you replied"). */
export function SystemNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-center py-1">
      <p className="rounded-full border border-line bg-panel px-3 py-1 text-center text-xs text-fg-secondary">{children}</p>
    </div>
  );
}
