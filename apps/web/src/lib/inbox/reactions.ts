import type { Message, Platform, ReactionEmoji } from "@/lib/api/types";

/** GR-42 (D4): the reactions a member can send, in the picker's order. */
export const REACTIONS: readonly ReactionEmoji[] = ["👍", "❤️", "😂", "😮", "😢", "🙏"];

/** What each platform takes: Instagram and Facebook only a heart (Meta's "love"); none elsewhere. */
export function reactionsFor(platform: Platform): readonly ReactionEmoji[] {
  if (platform === "whatsapp" || platform === "web") return REACTIONS;
  if (platform === "instagram" || platform === "facebook") return ["❤️"];
  return [];
}

/** The business's reaction to the message, if any. */
export function ourReaction(message: Message): string | null {
  return message.reactions.find((r) => r.by === "business")?.emoji ?? null;
}

/** The message with our reaction set (or removed with null), as the API will store it. */
export function withOurReaction(message: Message, emoji: string | null): Message {
  const others = message.reactions.filter((r) => r.by !== "business");
  const mine = emoji ? [{ emoji, by: "business" as const, at: new Date().toISOString() }] : [];
  return { ...message, reactions: [...others, ...mine] };
}

/** A message that reached the platform can be quoted or reacted to (the API needs its platform id). */
export function canActOn(message: Message): boolean {
  if (message.id.startsWith("local-") || message.deleted_at || message.direction === "system") return false;
  if (message.direction === "inbound") return true;
  return message.status === "sent" || message.status === "delivered" || message.status === "read";
}
