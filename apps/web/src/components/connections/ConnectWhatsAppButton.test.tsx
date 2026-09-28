import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { account, json, problem, renderWithApi, type Call } from "@/test/api";

import { ConnectWhatsAppButton } from "./ConnectWhatsAppButton";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

// Meta's SDK: FB.login answers with a code and Meta posts the session info.
const sdk = vi.hoisted(() => ({ outcome: "finish" as "finish" | "cancel" }));
vi.mock("@/lib/whatsapp/embedded-signup", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/whatsapp/embedded-signup")>();
  return {
    ...real,
    loadFacebookSdk: vi.fn(async () => ({
      init: () => {},
      login: (callback: (r: { authResponse: { code: string } | null }) => void) => {
        if (sdk.outcome === "cancel") return callback({ authResponse: null });
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: "https://www.facebook.com",
            data: JSON.stringify({
              type: "WA_EMBEDDED_SIGNUP",
              event: "FINISH",
              data: { phone_number_id: "1098765", waba_id: "2045678" },
            }),
          }),
        );
        callback({ authResponse: { code: "AQB-code" } });
      },
    })),
  };
});

async function renderButton(handler: (call: Call) => Response) {
  vi.stubEnv("NEXT_PUBLIC_META_APP_ID", "123");
  vi.stubEnv("NEXT_PUBLIC_WHATSAPP_CONFIG_ID", "cfg-1");
  return renderWithApi(<ConnectWhatsAppButton wid="w1" />, {
    handlers: { "POST /v1/w/:wid/social-accounts/whatsapp/embedded-signup": handler },
  });
}

beforeEach(() => {
  sdk.outcome = "finish";
  toast.mockClear();
  toast.success.mockClear();
  toast.error.mockClear();
});
afterEach(() => vi.unstubAllEnvs());

describe("Connect WhatsApp (F-04)", () => {
  it("sends the code and ids to the API and names the number", async () => {
    const { calls } = await renderButton(() =>
      json(account({ id: "a2", platform: "whatsapp", display_name: "Maple Bakery", phone_number: "+91 98765 43210" }), 201),
    );
    await userEvent.click(screen.getByRole("button", { name: "Connect WhatsApp" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("WhatsApp connected: Maple Bakery (+91 98765 43210)"));
    expect(calls[0].body).toEqual({ code: "AQB-code", waba_id: "2045678", phone_number_id: "1098765" });
  });

  it("is disabled until the Meta app is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_WHATSAPP_CONFIG_ID", "");
    renderWithApi(<ConnectWhatsAppButton wid="w1" />);
    expect(screen.getByRole("button", { name: "Connect WhatsApp" })).toBeDisabled();
  });

  it("closing Meta's dialog makes no request and shows a neutral toast", async () => {
    sdk.outcome = "cancel";
    const { calls } = await renderButton(() => json({}, 201));
    await userEvent.click(screen.getByRole("button", { name: "Connect WhatsApp" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Connection cancelled"));
    expect(calls).toHaveLength(0);
  });

  it("a number connected elsewhere gets the §4.7 copy", async () => {
    await renderButton(() => problem(409, "account_in_use", "In use"));
    await userEvent.click(screen.getByRole("button", { name: "Connect WhatsApp" }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "This account is connected to another Social Hood workspace. Disconnect it there first.",
      ),
    );
  });
});
