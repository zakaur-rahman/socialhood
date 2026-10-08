import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Conversation } from "@/lib/api/types";
import { conversation, json, renderWithApi } from "@/test/api";

import { DetailsPanel } from "./DetailsPanel";

function renderDetails(follows: boolean | null | undefined, overrides: Partial<Conversation> = {}) {
  const base = conversation(overrides);
  const detail: Conversation = { ...base, contact: { ...base.contact, follows_business: follows } };
  return renderWithApi(<DetailsPanel conversationId="c1" />, {
    handlers: { "GET /v1/w/:wid/conversations/:id": () => json(detail) },
  });
}

describe("DetailsPanel follow status (FR-AUT-22)", () => {
  it("says Follows you when Instagram reported it", async () => {
    renderDetails(true);
    const status = await screen.findByTestId("follow-status");
    expect(status).toHaveTextContent("Follows you");
    // UI-031: a status Badge in the brand (info) tone.
    expect(status).toHaveAttribute("data-slot", "badge");
    expect(status).toHaveAttribute("data-tone", "brand");
  });

  it("says Doesn't follow you when Instagram reported it", async () => {
    renderDetails(false);
    const status = await screen.findByTestId("follow-status");
    expect(status).toHaveTextContent("Doesn't follow you");
    expect(status).toHaveAttribute("data-tone", "neutral");
  });

  it("says nothing while it is unknown", async () => {
    renderDetails(null);
    expect(await screen.findByText("Priya Nair")).toBeInTheDocument();
    expect(screen.queryByTestId("follow-status")).toBeNull();
    expect(screen.queryByText(/follow you/)).toBeNull();
  });
});

// UI-031: the panel's groups are CardInsets (UI-ISS-036), the lead score a Meter (UI-ISS-037).
describe("DetailsPanel surfaces", () => {
  it("groups each section in a CardInset; the lead score is a slot Meter", async () => {
    renderDetails(true, { lead_score: 85 });
    const customer = await screen.findByRole("region", { name: "Customer" });
    const group = customer.querySelector('[data-slot="card-inset"]');
    expect(group).toHaveAttribute("data-padding", "compact");
    expect(group).toHaveClass("rounded-lg", "border-line");
    expect(group).not.toHaveClass("bg-field/60");
    const meter = customer.querySelector('[data-slot="meter"]');
    expect(meter).toHaveAttribute("data-kind", "slot");
    // A high score stays brand: a lead isn't a quota running out.
    expect(meter).toHaveAttribute("data-level", "normal");
    expect(screen.getByRole("meter", { name: "Lead score" })).toHaveAttribute("aria-valuetext", "85 of 100");
    expect(screen.getAllByRole("region").every((region) => region.querySelector('[data-slot="card-inset"]'))).toBe(true);
  });

  it("Open in Instagram is the link Button, 24 px (40 px on touch)", async () => {
    renderDetails(true);
    const open = await screen.findByRole("link", { name: /Open in Instagram/ });
    expect(open).toHaveAttribute("data-slot", "button");
    expect(open).toHaveAttribute("data-variant", "link");
    expect(open).toHaveAttribute("data-size", "xs");
  });
});
