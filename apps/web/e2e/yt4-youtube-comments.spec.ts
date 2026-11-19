import { expect, test } from "./support/fixtures";

/**
 * YT4 (YouTube Phase 4) YouTube comments on the sandbox, no Google call. The sandbox inbound route
 * gives the sandbox channel a video ("sandbox_yt_demo") and queues a comment poll, which finds the
 * sandbox's seeded viewer comment: "Love this! Where can I buy the starter you used?" by Sandbox
 * Viewer, with 12 likes, so it is Important before any analysis. A person replies from the post
 * page; there is no DM option on YouTube, and once answered it is no longer Important.
 */
type Post = { id: string; platform_media_id: string };
type Comment = { id: string; text: string; important: boolean };

test.describe("YT4 YouTube comments", () => {
  test("a polled YouTube comment shows as Important, and a person replies to it", async ({ api, page, youtube }) => {
    const { workspace, account } = youtube;
    // The route needs a text; on YouTube the poll finds the sandbox's own seeded comment instead.
    await api.inbound(workspace.id, { accountId: account.id, kind: "comment", text: "Love this!" });

    const posts = () => api.call<{ items: Post[] }>("GET", `/v1/w/${workspace.id}/posts?account_id=${account.id}`);
    let postId = "";
    await expect
      .poll(
        async () => {
          const post = (await posts()).items.find((p) => p.platform_media_id === "sandbox_yt_demo");
          if (!post) return 0;
          postId = post.id;
          const comments = await api.call<{ items: Comment[] }>("GET", `/v1/w/${workspace.id}/posts/${post.id}/comments`);
          return comments.items.length;
        },
        { timeout: 45_000, intervals: [1_000] },
      )
      .toBe(1);

    await page.goto(`/w/${workspace.slug}/comments/${postId}`);
    const row = page.getByRole("listitem", { name: "Comment by Sandbox Viewer" });
    await expect(row).toContainText("Love this! Where can I buy the starter you used?");
    await expect(row.getByText("Important", { exact: true })).toBeVisible();
    await expect(row.getByRole("button", { name: /^DM / })).toHaveCount(0);

    const chips = page.getByRole("radiogroup", { name: "Filter comments" });
    await expect(chips.getByRole("radio", { name: /Important/ })).toBeVisible();

    await row.getByRole("button", { name: /^Reply to / }).click();
    await row.getByRole("textbox").fill("Thanks! It's in the link in the description.");
    await row.getByRole("button", { name: "Send reply" }).click();
    await expect(row.getByTestId("public-reply")).toContainText("Thanks! It's in the link in the description.");
    await expect(row.getByText("Important", { exact: true })).toHaveCount(0);
  });
});
