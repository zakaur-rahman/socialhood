import { expect, test } from "./support/fixtures";

/**
 * C-165 phase B: the page an AI app links to, where a member drops the file it asked for. The API's
 * ticket routes are answered by the test (a ticket is made by an AI app over MCP, which e2e does not
 * run), so this checks the page itself: it shows what was asked for, refuses a file of the wrong
 * kind before uploading, and fits a phone without sideways scroll. Written, not run, by phase B.
 */
const TICKET = {
  id: "7d444840-9dc0-4f3f-9b36-0d6c6f0f5d1a",
  kind: "video",
  status: "waiting",
  expires_at: "2099-01-01T00:00:00Z",
  reason: null,
  media_asset_id: null,
  limits: { formats: ["mp4", "mov"], max_mb: 100 },
  upload: {
    cloud_name: "demo",
    api_key: "123",
    timestamp: 1,
    folder: "ws/x/post",
    tags: "mcp_upload_7d444840",
    signature: "sig",
    upload_url: "https://api.cloudinary.com/v1_1/demo/video/upload",
  },
};

test.describe("C-165 upload page for AI apps", () => {
  test("shows the ask, refuses the wrong kind, and fits a phone", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.route(`**/v1/w/${workspace.id}/mcp-uploads/${TICKET.id}`, (route) =>
      route.fulfill({ json: TICKET }),
    );
    await page.goto(`/w/${workspace.slug}/upload/${TICKET.id}`);
    await expect(page.getByRole("heading", { name: "Upload a file", level: 1 })).toBeVisible();
    await expect(page.getByText("Your AI app asked for a video.")).toBeVisible();

    await page
      .getByLabel("Choose a file")
      .setInputFiles({ name: "photo.jpg", mimeType: "image/jpeg", buffer: Buffer.from("x") });
    await expect(page.getByRole("alert").filter({ hasText: "Use an MP4 or MOV file." })).toBeVisible();

    for (const width of [375, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    }
  });

  test("says when the file is already in the library", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.route(`**/v1/w/${workspace.id}/mcp-uploads/${TICKET.id}`, (route) =>
      route.fulfill({ json: { ...TICKET, status: "uploaded", upload: null } }),
    );
    await page.goto(`/w/${workspace.slug}/upload/${TICKET.id}`);
    await expect(page.getByText("The file is in your media library.")).toBeVisible();
  });
});
