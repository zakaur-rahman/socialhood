import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { account, json, problem, renderWithApi, type Call } from "@/test/api";

import { ConnectWhatsAppButton } from "./ConnectWhatsAppButton";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

// Meta's SDK: FB.login answers with a code and Meta posts the session info: both ids (FINISH),
// the account only (FINISH_ONLY_WABA), or a finish naming neither.
const sdk = vi.hoisted(() => ({ outcome: "finish" as "finish" | "only_waba" | "no_ids" | "cancel" }));
vi.mock("@/lib/whatsapp/embedded-signup", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/whatsapp/embedded-signup")>();
  const sessionInfo = {
    finish: { event: "FINISH", data: { phone_number_id: "1098765", waba_id: "2045678" } },
    only_waba: { event: "FINISH_ONLY_WABA", data: { waba_id: "2045678" } },
    no_ids: { event: "FINISH_GRANT_ONLY_API_ACCESS", data: {} },
  };
  return {
    ...real,
    loadFacebookSdk: vi.fn(async () => ({
      init: () => {},
      login: (callback: (r: { authResponse: { code: string } | null }) => void) => {
        if (sdk.outcome === "cancel") return callback({ authResponse: null });
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: "https://www.facebook.com",
            data: JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", ...sessionInfo[sdk.outcome] }),
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

  it.each([
    ["only_waba", { code: "AQB-code", waba_id: "2045678" }],
    ["no_ids", { code: "AQB-code" }],
  ] as const)("a finish without every id (%s) still completes, sending the ids it has", async (outcome, body) => {
    sdk.outcome = outcome;
    const { calls } = await renderButton(() =>
      json(account({ id: "a2", platform: "whatsapp", display_name: "Maple Bakery", phone_number: "+91 98765 43210" }), 201),
    );
    await userEvent.click(screen.getByRole("button", { name: "Connect WhatsApp" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("WhatsApp connected: Maple Bakery (+91 98765 43210)"));
    expect(calls[0].body).toEqual(body);
  });

  it.each([
    [
      "wa_no_phone_number",
      "This WhatsApp Business Account has no phone number yet. Add and verify one in Meta's popup or in WhatsApp Manager, then connect again. Meta's test numbers can't be connected this way; use a number your business owns.",
    ],
    [
      "wa_choose_number",
      "This WhatsApp Business Account has more than one number. Connect again and pick the one to use in Meta's popup.",
    ],
    [
      "wa_choose_business_account",
      "Meta didn't say which WhatsApp Business Account to connect. Connect again and choose one in Meta's popup.",
    ],
  ])("the API's %s gets its copy", async (code, message) => {
    sdk.outcome = "only_waba";
    await renderButton(() => problem(422, code, "from the API"));
    await userEvent.click(screen.getByRole("button", { name: "Connect WhatsApp" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
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
