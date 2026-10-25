import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { json, renderWithApi } from "@/test/api";

import { PERMISSION, useCan } from "./permissions";

function Probe() {
  const { can, ready } = useCan();
  return (
    <div>
      <p>{ready ? "ready" : "loading"}</p>
      {can(PERMISSION.manageAutomations) ? <button>Edit automations</button> : null}
      {can(PERMISSION.reply) ? <button>Reply</button> : null}
    </div>
  );
}

describe("can() (GR-19)", () => {
  it("shows what the API grants and hides the rest", async () => {
    renderWithApi(<Probe />, {
      handlers: { "GET /v1/w/:wid/permissions": () => json({ role: "agent", permissions: ["inbox.reply"] }) },
    });
    expect(await screen.findByText("ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reply" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit automations" })).not.toBeInTheDocument();
  });

  it("allows nothing while the list loads", () => {
    renderWithApi(<Probe />, {
      handlers: { "GET /v1/w/:wid/permissions": () => new Promise<Response>(() => {}) },
    });
    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
