import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Link from "next/link";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LEAVE_WARNING } from "@/components/settings/SaveBar";
import type { AiSettings } from "@/lib/api/types";
import { aiSettings, json, renderWithApi, type Call } from "@/test/api";

import { BrandVoiceCard } from "./BrandVoiceCard";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

/** The sidebar's Inbox link; jsdom can't navigate, so reaching its click is "leaving". */
function SidebarLink({ onNavigate }: { onNavigate: () => void }) {
  return (
    <Link
      href="/w/maple/inbox"
      onClick={(event) => {
        event.preventDefault();
        onNavigate();
      }}
    >
      Inbox
    </Link>
  );
}

function setup(settings: AiSettings = aiSettings()) {
  const navigated = vi.fn();
  renderWithApi(
    <>
      <SidebarLink onNavigate={navigated} />
      <BrandVoiceCard wid="w1" settings={settings} workspaceName="Maple Bakery" />
    </>,
    { handlers: { "PUT /v1/w/:wid/ai-settings": (call: Call) => json({ ...settings, ...(call.body as object) }) } },
  );
  const leave = () => userEvent.click(screen.getByRole("link", { name: "Inbox" }));
  return { navigated, leave };
}

afterEach(() => vi.restoreAllMocks());

describe("BrandVoiceCard leaving with unsaved changes (UI-ISS-022)", () => {
  it("asks before a sidebar link leaves unsaved changes; staying keeps them", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { navigated, leave } = setup();
    const description = screen.getByRole("textbox", { name: "Business description" });
    await user.type(description, "Handmade linen dresses.");

    await leave();
    expect(confirm).toHaveBeenCalledWith(LEAVE_WARNING);
    expect(navigated).not.toHaveBeenCalled();
    expect(description).toHaveValue("Handmade linen dresses.");

    confirm.mockReturnValue(true);
    await leave();
    expect(navigated).toHaveBeenCalledOnce();
  });

  it("leaves without asking when nothing changed, and once the changes are saved", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { navigated, leave } = setup();
    await leave();
    expect(navigated).toHaveBeenCalledOnce();

    await user.type(screen.getByRole("textbox", { name: "Business description" }), "Handmade linen dresses.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Brand voice saved"));
    await leave();
    expect(navigated).toHaveBeenCalledTimes(2);
    expect(confirm).not.toHaveBeenCalled();
  });
});
