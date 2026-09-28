"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";
import { useCompleteWhatsAppSignup } from "@/lib/api/queries";
import { errorMessage, whatsappConnected } from "@/lib/copy";
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
  if (error instanceof ApiError && error.code === "account_in_use") {
    return "This account is connected to another Social Hood workspace. Disconnect it there first.";
  }
  // Other refusals (Meta's weekly onboarding allowance, plan limits) carry their copy in detail.
  return errorMessage(error);
}

/**
 * F-04: loads Meta's SDK on first use (only on this page), runs Embedded Signup, sends the
 * code and ids to the API, and names the connected number. Used to connect and to reconnect.
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
      complete.mutate(
        { code: result.code, waba_id: result.waba_id, phone_number_id: result.phone_number_id },
        {
          onSuccess: (account) => toast.success(whatsappConnected(account.display_name, account.phone_number)),
          onError: (error) => toast.error(whatsappSignupError(error)),
        },
      );
    } catch (error) {
      toast.error(error instanceof Error && !(error instanceof ApiError) ? error.message : errorMessage(error));
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
      disabled={!configured || busy}
      title={configured ? undefined : "WhatsApp isn't set up for this app yet"}
      onClick={connect}
    >
      <WhatsAppGlyph className="size-4" />
      {busy ? "Opening WhatsApp…" : "Connect WhatsApp"}
    </Button>
  );
}
