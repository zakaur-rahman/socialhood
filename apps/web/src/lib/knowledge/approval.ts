import type { KnowledgeSource } from "@/lib/api/types";

/** Waiting sources first; otherwise the order the API gave (the sort is stable). */
export function waitingFirst<T extends Pick<KnowledgeSource, "status">>(items: readonly T[]): T[] {
  const waiting = (item: T) => Number(item.status === "awaiting_approval");
  return [...items].sort((a, b) => waiting(b) - waiting(a));
}

/** The Sources card's description. */
export function waitingLine(count: number): string {
  return count === 1
    ? "1 from an AI app is waiting for approval."
    : `${count} from AI apps are waiting for approval.`;
}

/** Home's banner, where "sources" isn't already said by the card around it. */
export function waitingTitle(count: number): string {
  return count === 1
    ? "1 source from an AI app is waiting for approval"
    : `${count} sources from AI apps are waiting for approval`;
}
