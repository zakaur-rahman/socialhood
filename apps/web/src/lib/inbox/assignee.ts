import type { Assignee } from "@/lib/api/types";

/** Two letters for an assignee's avatar: the first of the first two words of their name. */
export function assigneeInitials(name: string | null | undefined): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters = words.length === 1 ? [words[0]] : [words[0], words[1]];
  return letters.map((word) => Array.from(word)[0] ?? "").join("").toUpperCase();
}

/**
 * How an assignee is named. The API names them when it can; a live update that could not look them
 * up carries only the id, so the name falls back to the members already loaded.
 */
export function assigneeName(assignee: Assignee, known?: { user_id: string; name: string | null }[]): string {
  return assignee.name ?? known?.find((member) => member.user_id === assignee.user_id)?.name ?? "A team member";
}
