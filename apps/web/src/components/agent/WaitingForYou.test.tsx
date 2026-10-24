import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { json, problem, renderWithApi } from "@/test/api";
import { approval } from "@/test/agent";

import { WaitingForYou } from "./WaitingForYou";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/w/maple/ask",
}));

const now = new Date("2026-09-29T12:00:00Z");

type Handlers = NonNullable<Parameters<typeof renderWithApi>[1]>["handlers"];

function show(handlers: Handlers) {
  renderWithApi(<WaitingForYou wid="w1" slug="maple" timeZone="Asia/Kolkata" now={now} />, { handlers });
}

describe("Waiting for you (GR-36)", () => {
  it("lists what is waiting with a count, and each can be approved or rejected there", async () => {
    show({
      "GET /v1/w/:wid/agent/approvals": (call) => {
        expect(call.url.searchParams.get("status")).toBe("pending");
        return json({
          items: [
            approval(),
            approval({ id: "ap2", tool: "propose_segment", summary: "New segment: VIPs with email", lines: ["Has the tag vip"] }),
          ],
          next_cursor: null,
        });
      },
    });
    const section = await screen.findByRole("region", { name: "Waiting for you" });
    expect(within(section).getByLabelText("2 waiting")).toBeInTheDocument();
    expect(within(section).queryByTestId("waiting-item")).not.toBeInTheDocument(); // collapsed

    await userEvent.click(within(section).getByRole("button", { name: /Waiting for you/ }));
    const items = within(section).getAllByTestId("waiting-item");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("New automation: Price list on PRICE");
    expect(items[0]).toHaveTextContent("Asked: When someone comments PRICE");
    expect(items[1]).toHaveTextContent("Has the tag vip");
    expect(within(items[1]).getByRole("button", { name: /Approve/ })).toBeEnabled();
    expect(within(items[1]).getByRole("button", { name: /Reject/ })).toBeEnabled();
  });

  it("shows nothing when nothing is waiting", async () => {
    let asked = false;
    show({
      "GET /v1/w/:wid/agent/approvals": () => {
        asked = true;
        return json({ items: [], next_cursor: null });
      },
    });
    await waitFor(() => expect(asked).toBe(true));
    expect(screen.queryByRole("region", { name: "Waiting for you" })).not.toBeInTheDocument();
  });

  it("shows nothing when it can't load (the answer's own card still has the controls)", async () => {
    let asked = false;
    show({
      "GET /v1/w/:wid/agent/approvals": () => {
        asked = true;
        return problem(500, "internal");
      },
    });
    await waitFor(() => expect(asked).toBe(true));
    expect(screen.queryByRole("region", { name: "Waiting for you" })).not.toBeInTheDocument();
  });

  it("a team member sees Approve disabled", async () => {
    show({ "GET /v1/w/:wid/agent/approvals": () => json({ items: [approval({ can_decide: false })], next_cursor: null }) });
    await userEvent.click(await screen.findByRole("button", { name: /Waiting for you/ }));
    expect(screen.getByRole("button", { name: /Approve/ })).toBeDisabled();
  });
});
