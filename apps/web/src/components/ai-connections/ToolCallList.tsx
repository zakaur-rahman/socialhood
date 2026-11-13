import { Badge } from "@/components/ui/badge";
import type { AiConnectionCall } from "@/lib/api/types";
import { relativeTime } from "@/lib/time";

const OUTCOME: Record<AiConnectionCall["outcome"], { label: string; tone: "success" | "warning" | "danger" }> = {
  ok: { label: "Done", tone: "success" },
  refused: { label: "Refused", tone: "warning" },
  error: { label: "Failed", tone: "danger" },
};

/** The recent tool calls of a connected app or an API key: outcome, tool and when. Never the arguments. */
export function ToolCallList({
  calls,
  label,
  empty = "No tool calls yet.",
}: {
  calls: AiConnectionCall[];
  label: string;
  empty?: string;
}) {
  if (calls.length === 0) return <p className="text-xs text-fg-secondary">{empty}</p>;
  return (
    <ol className="space-y-1" aria-label={label}>
      {calls.map((call) => (
        <li key={call.id} className="flex flex-wrap items-center gap-2 text-xs">
          <Badge tone={OUTCOME[call.outcome].tone}>{OUTCOME[call.outcome].label}</Badge>
          <code className="font-mono">{call.tool}</code>
          <span className="text-fg-secondary">{relativeTime(call.created_at)}</span>
        </li>
      ))}
    </ol>
  );
}
