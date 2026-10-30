import { expect, test } from "./support/fixtures";

/**
 * C-158: the sign-in and sign-up pages render Clerk's card without errors, carry the quiet legal line
 * (the public Terms and Privacy Policy; relative with one origin, as e2e runs), and on sign-up show
 * exactly one of its two lines: the consent sentence while Clerk's "Require express consent" is off,
 * "Terms · Privacy" once Clerk's own checkbox is on the card. No sideways scroll on a phone or a wide
 * screen, and the pages stay out of search.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = [
  { path: "/sign-in", title: /sign in/i },
  { path: "/sign-up", title: /create your/i },
] as const;

test.describe("C-158 auth pages", () => {
  for (const { path, title } of PAGES) {
    test(`${path} renders Clerk's card and the legal links`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));

      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
      await expect(page.locator('meta[name="robots"]').first()).toHaveAttribute("content", /noindex/);

      const legal = page.getByRole("navigation", { name: "Legal" });
      const terms = legal.getByRole("link", { name: /^Terms/ }).filter({ visible: true });
      const privacy = legal.getByRole("link", { name: /^Privacy/ }).filter({ visible: true });
      await expect(terms).toHaveCount(1);
      await expect(privacy).toHaveCount(1);
      await expect(terms).toHaveAttribute("href", "/terms");
      await expect(privacy).toHaveAttribute("href", "/privacy");
      await expect(terms).toHaveAttribute("target", "_blank");

      if (path === "/sign-up") {
        const sentence = legal.getByText(/By continuing, you agree to our/);
        const consent = page.locator("#legalAccepted-field");
        // Whichever Clerk shows, exactly one wording is on screen.
        if (await consent.count()) {
          await expect(sentence).toBeHidden();
          await expect(page.locator(".cl-formFieldCheckboxLabel a")).toHaveCount(2);
        } else {
          await expect(sentence).toBeVisible();
        }
      }

      for (const width of [375, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      }
      expect(errors).toEqual([]);
    });
  }

  test("the logo goes back to the public site", async ({ page }) => {
    await page.goto("/sign-in");
    await expect(page.getByRole("link", { name: "Amplychat" }).filter({ visible: true })).toHaveAttribute("href", "/");
  });
});
