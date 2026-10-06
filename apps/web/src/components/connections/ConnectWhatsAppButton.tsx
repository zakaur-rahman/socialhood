"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";
import { useCompleteWhatsAppSignup } from "@/lib/api/queries";
import { errorMessage, whatsappConnectError, whatsappConnected } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { loadFacebookSdk, runEmbeddedSignup } from "@/lib/whatsapp/embedded-signup";

import { WhatsAppGlyph } from "./WhatsAppGlyph";

/** Next inlines NEXT_PUBLIC_ values at build time wherever they are read. */
function metaConfig() {
  return {
    appId: process.env.NEXT_PUBLIC_META_APP_ID ?? "",
    configId: process.env.NEXT_PUBLIC_WHATSAPP_CONFIG_ID ?? "",
  };
}

/** The copy for a failed Embedded Signup completion (F-04 edge cases, §4.7). */
export function whatsappSignupError(error: unknown): string {
  if (error instanceof ApiError) {
    const copy = whatsappConnectError(error.code);
    if (copy) return copy;
  }
  // Other refusals (Meta's weekly onboarding allowance) carry their copy in detail; a plan limit
  // (402) is the upgrade dialog's.
  return errorMessage(error);
}

/**
 * F-04: loads Meta's SDK on first use (only on this page), runs Embedded Signup, sends the
 * code and whichever ids Meta's session info gave to the API (it finds the rest), and names the
 * connected number. Used to connect and to reconnect.
 */
export function useWhatsAppConnect(wid: string) {
  const complete = useCompleteWhatsAppSignup(wid);
  const [opening, setOpening] = useState(false);

  const { appId, configId } = metaConfig();

  const connect = async () => {
    setOpening(true);
    try {
      const fb = await loadFacebookSdk(appId);
      const result = await runEmbeddedSignup(fb, configId);
      if (result.kind === "cancelled") {
        toast("Connection cancelled"); // neutral: no request was made
        return;
      }
      if (result.kind === "error") {
        toast.error(result.message);
        return;
      }
      const { code, waba_id, phone_number_id } = result;
      complete.mutate(
        { code, ...(waba_id ? { waba_id } : {}), ...(phone_number_id ? { phone_number_id } : {}) },
        {
          onSuccess: (account) => toast.success(whatsappConnected(account.display_name, account.phone_number)),
          // Over accounts_per_platform (402): the upgrade dialog says so.
          onError: (error) => toastError(error, whatsappSignupError(error)),
        },
      );
    } catch (error) {
      toastError(error, error instanceof Error && !(error instanceof ApiError) ? error.message : undefined);
    } finally {
      setOpening(false);
    }
  };

  return {
    connect: () => void connect(),
    busy: opening || complete.isPending,
    configured: Boolean(appId && configId),
  };
}

export function ConnectWhatsAppButton({ wid }: { wid: string }) {
  const { connect, busy, configured } = useWhatsAppConnect(wid);
  return (
    <Button
      variant="secondary"
      className="min-h-10 px-4 md:min-h-9"
      disabled={!configured || busy}
      title={configured ? undefined : "WhatsApp isn't set up for this app yet"}
      onClick={connect}
    >
      <WhatsAppGlyph className="size-4" />
      {busy ? "Opening WhatsApp…" : "Connect WhatsApp"}
    </Button>
  );
}
