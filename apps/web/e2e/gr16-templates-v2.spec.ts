import { expect, test } from "./support/fixtures";

/**
 * GR-16 The gallery has five templates that start as a flow: a story giveaway, a lead magnet,
 * a price by option, call requests and a coupon from an entry link. Each makes a draft saved as a
 * flow that activates once its link is filled in.
 */
type Flow = { source: string; definition: { steps: Array<{ buttons?: Array<{ url: string | null }> }> }; missing_for_activation: string[] };
type Run = { id: string; result: string };

const FLOW_TEMPLATES = [
  { key: "story_giveaway", name: "Story giveaway", steps: 2 },
  { key: "lead_magnet", name: "Lead magnet", steps: 2 },
  { key: "price_by_option", name: "Price by option", steps: 4 },
  { key: "call_request", name: "Call requests", steps: 2 },
  { key: "entry_link_coupon", name: "Coupon from a link", steps: 1 },
];

test.describe("GR-16 template gallery, version 2", () => {
  for (const template of FLOW_TEMPLATES) {
    test(`${template.name} starts as a flow and activates once filled`, async ({ api, sandbox }) => {
      const { workspace, account } = sandbox;
      const base = `/v1/w/${workspace.id}/automations`;
      const draft = await api.call<{ id: string; template_key: string; flow_source: string }>("POST", base, {
        template_key: template.key,
        social_account_id: account.id,
      });
      expect(draft.template_key).toBe(template.key);
      expect(draft.flow_source).toBe("flow");

      const flow = await api.call<Flow>("GET", `${base}/${draft.id}/flow`);
      expect(flow.source).toBe("flow");
      expect(flow.definition.steps).toHaveLength(template.steps);

      // The link is the only thing the user must fill in.
      for (const step of flow.definition.steps) {
        for (const button of step.buttons ?? []) button.url = "https://example.com/offer";
      }
      const saved = await api.call<Flow>("PUT", `${base}/${draft.id}/flow`, flow.definition);
      expect(saved.missing_for_activation).toEqual([]);
      const active = await api.call<{ status: string }>("POST", `${base}/${draft.id}/activate`);
      expect(active.status).toBe("active");
    });
  }

  test("the gallery lists them with their steps, and a card opens the editor on a draft", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.goto(`/w/${workspace.slug}/automations`);
    await page.getByRole("button", { name: "New automation" }).first().click();
    const dialog = page.getByRole("dialog", { name: "New automation" });
    for (const template of FLOW_TEMPLATES) {
      await expect(dialog.getByRole("article", { name: template.name })).toContainText(
        template.steps === 1 ? "1 step" : `${template.steps} steps`,
      );
    }
    await dialog.getByRole("button", { name: "Use template: Coupon from a link" }).click();
    await expect(page).toHaveURL(/\/automations\/[0-9a-f-]+/, { timeout: 20_000 });
  });

  test("a call request answers a CALL message with its question", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setAiMode(workspace.id, account.id, "off");
    const base = `/v1/w/${workspace.id}/automations`;
    const draft = await api.call<{ id: string }>("POST", base, {
      template_key: "call_request",
      social_account_id: account.id,
    });
    await api.call("POST", `${base}/${draft.id}/activate`);
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text: "call",
      fromId: `e2e_gr16_${Date.now().toString(36)}`,
    });
    await expect
      .poll(async () => (await api.call<{ items: Run[] }>("GET", `${base}/${draft.id}/runs`)).items.length, { timeout: 30_000 })
      .toBe(1);
  });
});
