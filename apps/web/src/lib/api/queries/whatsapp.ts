"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { EmbeddedSignup, SocialAccount, WhatsAppTemplate } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** Approved templates for sends outside the 24 h window (FR-INB-10). */
export function useWhatsAppTemplates(wid: string, accountId: string, enabled = true) {
  const api = useApi();
  return useQuery<WhatsAppTemplate[]>({
    queryKey: keys.templates(wid, accountId),
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (
        await unwrap(
          api.GET("/v1/w/{wid}/social-accounts/{account_id}/templates", {
            params: { path: { wid, account_id: accountId } },
          }),
        )
      ).items,
  });
}

/** F-04: hand the Embedded Signup result to the API, which stores the number. */
export function useCompleteWhatsAppSignup(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SocialAccount, Error, EmbeddedSignup>({
    mutationFn: (body) =>
      unwrap(api.POST("/v1/w/{wid}/social-accounts/whatsapp/embedded-signup", { params: { path: { wid } }, body })),
    onSuccess: async (account) => {
      queryClient.setQueryData<SocialAccount[]>(keys.accounts(wid), (items) =>
        items ? [...items.filter((item) => item.id !== account.id), account] : items,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.accounts(wid) }),
        queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] }),
      ]);
    },
  });
}
