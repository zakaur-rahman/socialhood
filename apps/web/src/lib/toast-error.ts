import { toast } from "sonner";

import { isPlanLimitError } from "@/lib/api/errors";
import { errorMessage } from "@/lib/copy";

/**
 * A failed request as a toast, except a plan limit (402): every 402 from a query or mutation opens
 * the upgrade dialog (lib/api/provider.tsx), which names the limit, so a toast would say it twice
 * (T8.4, C-051). `message` is the screen's own words, else the error's copy. eslint refuses
 * `toast.error(errorMessage(e))`, so failed requests come through here (UI-024).
 */
export function toastError(error: unknown, message?: string): void {
  if (isPlanLimitError(error)) return;
  toast.error(message ?? errorMessage(error));
}
