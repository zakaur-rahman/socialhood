"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/states/EmptyState";
import { SearchInput } from "@/components/ui/search-input";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

/**
 * A small emoji picker, loaded only when the composer's emoji button is first used
 * (TR-FE-08). Business replies need a few hundred common emoji, not the full Unicode set, so
 * this ships its own list styled with the tokens instead of a third-party picker.
 */
const GROUPS: { name: string; emoji: [string, string][] }[] = [
  {
    name: "Smileys",
    emoji: [
      ["😀", "grin smile happy"], ["😃", "smile happy"], ["😄", "smile laugh"], ["😁", "grin beam"],
      ["😆", "laugh"], ["😅", "sweat laugh"], ["😂", "joy tears laugh"], ["🤣", "rofl laugh"],
      ["😊", "blush smile"], ["😇", "angel innocent"], ["🙂", "slight smile"], ["😉", "wink"],
      ["😍", "love heart eyes"], ["🥰", "love hearts"], ["😘", "kiss"], ["😋", "yum tasty"],
      ["😎", "cool sunglasses"], ["🤩", "star struck wow"], ["🥳", "party celebrate"], ["🤗", "hug"],
      ["🤔", "think hmm"], ["😐", "neutral"], ["🙄", "eye roll"], ["😏", "smirk"],
      ["😌", "relieved"], ["😴", "sleep"], ["😮", "wow surprised"], ["😲", "astonished"],
      ["🥺", "pleading please"], ["😢", "cry sad"], ["😭", "sob cry"], ["😤", "huff"],
      ["😡", "angry"], ["🤯", "mind blown"], ["😳", "flushed"], ["🤭", "oops giggle"],
      ["🤫", "shush quiet"], ["🙃", "upside down"], ["😬", "grimace"], ["🤝", "handshake deal"],
    ],
  },
  {
    name: "Gestures",
    emoji: [
      ["👍", "thumbs up yes ok"], ["👎", "thumbs down no"], ["👌", "ok perfect"], ["✌️", "peace victory"],
      ["🤞", "fingers crossed luck"], ["🙏", "thanks please pray"], ["👏", "clap applause"], ["🙌", "raised hands yay"],
      ["👋", "wave hello bye"], ["🤙", "call me"], ["💪", "strong muscle"], ["👉", "point right"],
      ["👈", "point left"], ["👆", "point up"], ["👇", "point down"], ["✋", "hand stop"],
      ["🫶", "heart hands love"], ["🤲", "palms"], ["✍️", "writing"], ["👀", "eyes look"],
    ],
  },
  {
    name: "Hearts",
    emoji: [
      ["❤️", "red heart love"], ["🧡", "orange heart"], ["💛", "yellow heart"], ["💚", "green heart"],
      ["💙", "blue heart"], ["💜", "purple heart"], ["🖤", "black heart"], ["🤍", "white heart"],
      ["💕", "two hearts"], ["💖", "sparkling heart"], ["💯", "hundred perfect"], ["✨", "sparkles"],
      ["⭐", "star"], ["🌟", "glowing star"], ["🔥", "fire hot lit"], ["🎉", "party tada celebrate"],
    ],
  },
  {
    name: "Shopping",
    emoji: [
      ["🛍️", "shopping bags"], ["🛒", "cart"], ["💳", "card payment"], ["💰", "money bag"],
      ["💸", "money"], ["🏷️", "tag price label"], ["🎁", "gift present"], ["📦", "package box parcel"],
      ["🚚", "delivery truck shipping"], ["✈️", "plane flight"], ["📍", "location pin"], ["🏠", "home house"],
      ["🕒", "clock time"], ["📅", "calendar date"], ["📞", "phone call"], ["📧", "email"],
      ["✅", "check done yes"], ["❌", "cross no"], ["⚠️", "warning"], ["ℹ️", "info"],
      ["👗", "dress"], ["👕", "shirt tshirt"], ["👟", "shoe sneaker"], ["💄", "lipstick makeup"],
      ["💍", "ring jewellery"], ["⌚", "watch"], ["📱", "phone mobile"], ["💻", "laptop"],
    ],
  },
  {
    name: "Food",
    emoji: [
      ["☕", "coffee"], ["🍵", "tea"], ["🍰", "cake"], ["🎂", "birthday cake"], ["🍪", "cookie"],
      ["🍕", "pizza"], ["🍔", "burger"], ["🍟", "fries"], ["🥗", "salad"], ["🍜", "noodles"],
      ["🍫", "chocolate"], ["🍩", "donut"], ["🍓", "strawberry"], ["🥭", "mango"], ["🍷", "wine"],
    ],
  },
];

export default function EmojiPicker({ onPick }: { onPick: (emoji: string) => void }) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return GROUPS.flatMap((group) => group.emoji).filter(([, words]) => words.includes(q));
  }, [query]);

  // The emoji's name is its aria-label; the picture says the rest, so no title tooltip on each.
  const button = ([emoji, words]: [string, string]) => (
    <button
      key={emoji}
      type="button"
      onClick={() => onPick(emoji)}
      aria-label={words.split(" ")[0]}
      className="grid size-8 place-items-center rounded-md text-lg hover:bg-pressed focus-visible:-outline-offset-2"
    >
      {emoji}
    </button>
  );

  // The SearchInput primitive (UI-031). Inside the composer's popover, Esc reaches the popover first,
  // so the popover's onEscapeKeyDown (lib/inbox/search-escape) empties a search with text before it
  // closes.
  return (
    <div className="flex w-72 flex-col gap-2">
      <SearchInput
        id="emoji-search"
        label="Search emoji"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search emoji"
        autoFocus
      />
      <div className="max-h-64 overflow-y-auto">
        {results ? (
          results.length ? (
            <div className="grid grid-cols-8 gap-0.5">{results.map(button)}</div>
          ) : (
            <EmptyState size="compact" title={`No emoji match "${query.trim()}"`} className="px-1 py-4" />
          )
        ) : (
          GROUPS.map((group) => (
            <section key={group.name} aria-label={group.name} className="mb-2">
              <h3 className={cn("mb-1 px-1", EYEBROW)}>
                {group.name}
              </h3>
              <div className="grid grid-cols-8 gap-0.5">{group.emoji.map(button)}</div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
