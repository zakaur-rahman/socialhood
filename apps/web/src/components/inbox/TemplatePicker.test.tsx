import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { WhatsAppTemplate } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { fillTemplate, TemplatePicker } from "./TemplatePicker";

const orderUpdate: WhatsAppTemplate = {
  name: "order_update",
  language: "en",
  category: "utility",
  status: "APPROVED",
  body: "Hi {{1}}, your order {{2}} has shipped.",
  param_count: 2,
};

function renderPicker(templates: WhatsAppTemplate[]) {
  const onSend = vi.fn();
  renderWithApi(<TemplatePicker wid="w1" accountId="a2" open onOpenChange={() => {}} onSend={onSend} />, {
    handlers: { "GET /v1/w/:wid/social-accounts/:id/templates": () => json({ items: templates }) },
  });
  return onSend;
}

describe("TemplatePicker (FR-INB-10, UX-INB-07)", () => {
  it("fills variables into the preview and sends the template", async () => {
    const user = userEvent.setup();
    const onSend = renderPicker([orderUpdate, { ...orderUpdate, name: "draft_promo", status: "PENDING" }]);
    await user.click(await screen.findByRole("button", { name: /order_update/ }));
    expect(screen.queryByRole("button", { name: /draft_promo/ })).not.toBeInTheDocument(); // only approved ones
    const send = screen.getByRole("button", { name: "Send template" });
    expect(send).toBeDisabled();

    await user.type(screen.getByLabelText("Variable {{1}}"), "Priya");
    await user.type(screen.getByLabelText("Variable {{2}}"), "#4821");
    expect(screen.getByText("Hi Priya, your order #4821 has shipped.")).toBeInTheDocument();
    await user.click(send);
    expect(onSend).toHaveBeenCalledWith({
      name: "order_update",
      language: "en",
      params: ["Priya", "#4821"],
      preview: "Hi Priya, your order #4821 has shipped.",
    });
  });

  it("explains when there are no approved templates", async () => {
    renderPicker([]);
    expect(await screen.findByText("No approved templates")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send template" })).toBeDisabled());
  });

  it("leaves unfilled variables visible in the preview", () => {
    expect(fillTemplate("Hi {{1}}, order {{2}}", ["Priya"])).toBe("Hi Priya, order {{2}}");
  });
});
