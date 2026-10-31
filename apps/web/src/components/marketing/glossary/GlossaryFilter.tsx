"use client";

import { Search } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { applyGlossaryFilter, type GlossaryChannelFilter } from "./glossary-filter";

/** Nothing to subscribe to: the value only changes from server to client. */
const noop = () => () => {};

const CHANNELS: { value: GlossaryChannelFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "WhatsApp", label: "WhatsApp" },
  { value: "Instagram", label: "Instagram" },
  { value: "Meta", label: "Both" },
];

/**
 * The glossary index's search and channel filter (C-163), a small client island. The server renders
 * every term, so without script the full A–Z list and its letter links work; this island fills a slot
 * whose height is reserved in CSS (`.gl-filter`), so nothing moves when it appears. It toggles
 * `hidden` on the list (`applyGlossaryFilter`) and says how many terms show in a polite live region.
 */
export function GlossaryFilter({ listId, total }: { listId: string; total: number }) {
  // False on the server and in the first client render, true once hydrated: the slot stays empty
  // until the filter can work.
  const ready = useSyncExternalStore(noop, () => true, () => false);
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState<GlossaryChannelFilter>("all");
  const [shown, setShown] = useState(total);

  const apply = (nextQuery: string, nextChannel: GlossaryChannelFilter) => {
    setQuery(nextQuery);
    setChannel(nextChannel);
    const root = document.getElementById(listId)?.closest("[data-glossary]") ?? document;
    setShown(applyGlossaryFilter(root, nextQuery, nextChannel));
  };

  if (!ready) return null;
  return (
    <div className="gl-filter-in" role="search" aria-label="Find a term">
      <label className="gl-search">
        <Search size={18} strokeWidth={1.75} aria-hidden focusable="false" />
        <span className="sr-only">Find a term</span>
        <input
          type="search"
          value={query}
          onChange={(event) => apply(event.target.value, channel)}
          placeholder="Find a term"
          autoComplete="off"
          spellCheck={false}
          aria-controls={listId}
        />
      </label>
      <div className="gl-chan" role="group" aria-label="Channel">
        {CHANNELS.map((item) => (
          <button key={item.value} type="button" aria-pressed={channel === item.value} onClick={() => apply(query, item.value)}>
            {item.label}
          </button>
        ))}
      </div>
      <p className="gl-count" aria-live="polite">
        {shown === total ? `${total} terms` : shown === 0 ? "No terms match" : `${shown} of ${total} terms`}
      </p>
    </div>
  );
}
