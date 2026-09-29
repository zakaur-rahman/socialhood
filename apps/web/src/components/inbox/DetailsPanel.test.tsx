import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Conversation } from "@/lib/api/types";
import { conversation, json, renderWithApi } from "@/test/api";

import { DetailsPanel } from "./DetailsPanel";

function renderDetails(follows: boolean | null | undefined) {
  const base = conversation();
  const detail: Conversation = { ...base, contact: { ...base.contact, follows_business: follows } };
  return renderWithApi(<DetailsPanel conversationId="c1" />, {
    handlers: { "GET /v1/w/:wid/conversations/:id": () => json(detail) },
  });
}

describe("DetailsPanel follow status (FR-AUT-22)", () => {
  it("says Follows you when Instagram reported it", async () => {
    renderDetails(true);
    expect(await screen.findByTestId("follow-status")).toHaveTextContent("Follows you");
  });

  it("says Doesn't follow you when Instagram reported it", async () => {
    renderDetails(false);
    expect(await screen.findByTestId("follow-status")).toHaveTextContent("Doesn't follow you");
  });

  it("says nothing while it is unknown", async () => {
    renderDetails(null);
    expect(await screen.findByText("Priya Nair")).toBeInTheDocument();
    expect(screen.queryByTestId("follow-status")).toBeNull();
    expect(screen.queryByText(/follow you/)).toBeNull();
  });
});
