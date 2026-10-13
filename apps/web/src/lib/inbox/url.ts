import type { InboxView } from "@/lib/api/types";

/**
 * The inbox's filters in the address (UI-052): `?view=` and `?platform=`, so Back, refresh, Copy
 * link and Home's tile all land on the same list. `view=all` is the default and stays out of the
 * address; `platform` is written whenever one is chosen, "all" included, because without it the
 * device's remembered platform applies.
 */
export type InboxUrlPatch = { view?: InboxView; platform?: string | null };

function parse(current: URLSearchParams | string): URLSearchParams {
  return new URLSearchParams(typeof current === "string" ? current : current.toString());
}

/** The query string (with its "?", or empty) after applying the patch; other parameters are kept. */
export function inboxSearch(current: URLSearchParams | string, patch: InboxUrlPatch = {}): string {
  const params = parse(current);
  if (patch.view !== undefined) {
    if (patch.view === "all") params.delete("view");
    else params.set("view", patch.view);
  }
  if (patch.platform !== undefined) {
    if (patch.platform === null) params.delete("platform");
    else params.set("platform", patch.platform);
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** Only the filters, for links to a conversation (they carry the list's filters along). */
export function inboxFilterSearch(current: URLSearchParams | string): string {
  const params = parse(current);
  const keep = new URLSearchParams();
  for (const key of ["view", "platform"]) {
    const value = params.get(key);
    if (value) keep.set(key, value);
  }
  const text = keep.toString();
  return text ? `?${text}` : "";
}
