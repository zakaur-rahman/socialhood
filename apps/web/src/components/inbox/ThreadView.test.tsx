import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { keys, type ConversationFilters } from "@/lib/api/queries/keys";
import type { Conversation, Message, SendMessage } from "@/lib/api/types";
import { resetInboxStore } from "@/lib/inbox/store";
import { account, conversation, json, listItem, message, noContent, problem, renderWithApi, type Call } from "@/test/api";

import { ThreadView } from "./ThreadView";

vi.mock("next/navigation", () => ({ usePathname: () => "/w/maple/inbox/c1" }));

const priya = conversation({ id: "c1" });
const kabir = conversation({
  id: "c2",
  contact: {
    id: "p2",
    display_name: "Kabir Shah",
    username: "kabir",
    profile_picture_url: null,
    first_seen_at: "2026-09-20T09:00:00Z",
    platform_user_id: "178",
  },
});

const threads: Record<string, Message[]> = {
  c1: [message({ id: "m1", conversation_id: "c1", text: "Do you ship to Dubai?", occurred_at: "2026-09-28T11:55:00Z" })],
  c2: [message({ id: "m2", conversation_id: "c2", text: "Is COD available?", occurred_at: "2026-09-28T10:00:00Z" })],
};

type SendHandler = (call: Call) => Response | Promise<Response>;

function handlers(onSend: SendHandler, conversations: Record<string, Conversation> = { c1: priya, c2: kabir }) {
  return {
    "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
    "GET /v1/w/:wid/conversations/:id": (_: Call, p: Record<string, string>) => json(conversations[p.id]),
    "GET /v1/w/:wid/conversations/:id/messages": (_: Call, p: Record<string, string>) =>
      json({ items: threads[p.id] ?? [], next_cursor: null }),
    "POST /v1/w/:wid/conversations/:id/messages": onSend,
    "POST /v1/w/:wid/conversations/:id/read": () => noContent(),
  };
}

function stored(call: Call, status: Message["status"] = "queued"): Message {
  const body = call.body as SendMessage;
  return message({
    id: "m-server",
    conversation_id: "c1",
    client_id: body.client_id,
    direction: "outbound",
    source: "human",
    text: body.text ?? null,
    status,
    occurred_at: "2026-09-28T12:00:00Z",
  });
}

async function replyWith(text: string) {
  const user = userEvent.setup();
  const box = await screen.findByRole("textbox", { name: /Reply to/ });
  await user.type(box, `${text}{Enter}`);
  return user;
}

beforeEach(() => resetInboxStore());

describe("ThreadView: optimistic send (TR-FE-05)", () => {
  it("posts with client_id as the Idempotency-Key; a network drop fails with Retry, which reuses the key", async () => {
    let attempts = 0;
    const { calls } = renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers((call) => {
        attempts += 1;
        if (attempts === 1) throw new TypeError("Failed to fetch");
        return json(stored(call), 202);
      }),
    });
    await screen.findByText("Do you ship to Dubai?");
    await replyWith("Yes, 5–7 days");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("You're offline. Reconnect to send messages.");
    await userEvent.click(within(alert).getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    const sends = calls.filter((c) => c.method === "POST" && c.path.endsWith("/messages"));
    expect(sends).toHaveLength(2);
    const [first, second] = sends;
    const key = first.headers.get("Idempotency-Key");
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
    expect(second.headers.get("Idempotency-Key")).toBe(key);
    expect(first.body).toEqual(second.body);
    expect((first.body as SendMessage).client_id).toBe(key);
    expect(screen.getAllByText("Yes, 5–7 days")).toHaveLength(1);
  });

  it("shows the mapped reason when the API refuses", async () => {
    renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers(() => problem(409, "reply_window_closed", "The reply window is closed.")),
    });
    await screen.findByText("Do you ship to Dubai?");
    await replyWith("Hello?");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Instagram allows replies for 24 hours after the customer's last message.");
    expect(within(alert).queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    await userEvent.click(within(alert).getByRole("button", { name: "Discard" }));
    expect(screen.queryByText("Hello?")).not.toBeInTheDocument();
  });

  it("shows the queued bubble at once, then the server's copy", async () => {
    let release: () => void = () => {};
    renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers(
        (call) =>
          new Promise<Response>((resolve) => {
            release = () => resolve(json(stored(call, "sent"), 202));
          }),
      ),
    });
    await screen.findByText("Do you ship to Dubai?");
    await replyWith("On its way");
    expect(await screen.findByRole("img", { name: "Queued" })).toBeInTheDocument();
    release();
    expect(await screen.findByRole("img", { name: "Sent" })).toBeInTheDocument();
    expect(screen.getAllByText("On its way")).toHaveLength(1);
  });
});

describe("ThreadView: state isolation (TR-FE-06, FR-INB-02)", () => {
  it("switching conversations shows none of the previous one's drafts or failed messages", async () => {
    const user = userEvent.setup();
    const view = renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers(() => problem(503, "platform_unavailable", "Instagram didn't respond.")),
    });
    await screen.findByText("Do you ship to Dubai?");
    await replyWith("This one fails");
    await screen.findByRole("alert");
    await user.type(screen.getByRole("textbox", { name: /Reply to/ }), "A draft for Priya");

    view.rerender(<ThreadView key="c2" conversationId="c2" />);
    await screen.findByText("Is COD available?");
    expect(screen.getByRole("textbox", { name: "Reply to Kabir Shah" })).toHaveValue("");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("This one fails")).not.toBeInTheDocument();
    expect(screen.queryByText("Do you ship to Dubai?")).not.toBeInTheDocument();

    // Back in Priya's conversation, her draft and her failed reply are still hers.
    view.rerender(<ThreadView key="c1" conversationId="c1" />);
    expect(await screen.findByRole("textbox", { name: "Reply to Priya Nair" })).toHaveValue("A draft for Priya");
    expect(screen.getByText("This one fails")).toBeInTheDocument();
  });
});

describe("ThreadView: read state (FR-INB-04)", () => {
  it("marks the conversation read when it opens, in every cached list", async () => {
    const filters: ConversationFilters = { view: "all", platform: null, accountId: null, q: "" };
    const unread = conversation({ id: "c1", unread_count: 2 });
    const { calls, queryClient } = renderWithApi(<ThreadView key="c1" conversationId="c1" />, {
      handlers: handlers(() => noContent(), { c1: unread }),
    });
    queryClient.setQueryData(keys.conversations("w1", filters), {
      pages: [{ items: [listItem({ id: "c1", unread_count: 2 })], next_cursor: null }],
      pageParams: [null],
    });
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/conversations/c1/read")).toBe(true));
    const list = queryClient.getQueryData<{ pages: { items: { unread_count: number }[] }[] }>(keys.conversations("w1", filters));
    expect(list?.pages[0].items[0].unread_count).toBe(0);
  });
});
