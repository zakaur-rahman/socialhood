import { expect, test } from "./support/fixtures";

/**
 * The landing page (C-155, C-157), signed out: the scenes have content before any script, they come
 * to life once it loads (the hero's scattered inbox sorts with the scroll on a wide screen and plays once
 * on a phone, How it works is live, the mode switch works,
 * the keyword field changes the automation), the sections come in the planned order, nothing scrolls
 * sideways, nothing loops without a pause control, and the page's layout shift stays under 0.1
 * (Google's "good") while it loads and is scrolled through.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const LIMIT = 0.1;
const VIEWPORTS = [
  { name: "phone", size: { width: 375, height: 800 } },
  { name: "tablet", size: { width: 768, height: 900 } },
  { name: "desktop", size: { width: 1280, height: 800 } },
  { name: "wide", size: { width: 1536, height: 900 } },
];

test.describe("landing page", () => {
  for (const { name, size } of VIEWPORTS) {
    test(`scenes are filled and live, layout is stable and fits (${name})`, async ({ page }) => {
      await page.setViewportSize(size);
      await page.addInitScript(() => {
        const w = window as unknown as { __cls: number };
        w.__cls = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) {
            if (!entry.hadRecentInput) w.__cls += entry.value;
          }
        }).observe({ type: "layout-shift", buffered: true });
      });
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

      // The scenes are in the markup before any scrolling: the sorted inbox, the knowledge, the comments.
      await expect(page.locator("[data-stage] .note")).toHaveCount(8);
      await expect(page.locator("[data-stage] .note .tag").first()).toHaveText("Needs you");
      await expect(page.locator("[data-kb] .line")).not.toHaveCount(0);
      await expect(page.locator("[data-comments] .cmt")).not.toHaveCount(0);
      // C-157 motion (the owner's call): the scroll-scrubbed hero is back. CSS says which driver applies.
      await expect(page.locator("[data-hero-scrub]")).toHaveCount(1);
      await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
      const heroMode = await page.locator("section.hero").evaluate((el) => getComputedStyle(el).getPropertyValue("--hero-mode").trim());
      if (size.width <= 900) {
        // Phones and tablets: it plays once when the inbox is on screen, then nothing runs there.
        expect(heroMode).toBe("play");
        await page.locator("[data-inbox]").scrollIntoViewIfNeeded();
        await expect(page.locator("[data-stage][data-play]")).toHaveCount(1, { timeout: 10_000 });
        await expect
          .poll(() => page.evaluate(() => document.querySelector("[data-stage]")!.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length), { timeout: 5_000 })
          .toBe(0);
        await page.evaluate(() => window.scrollTo(0, 0));
      } else {
        // A wide screen with a mouse: the scroll drives it (CSS scroll timeline, or the script without one).
        expect(["native", "scrub"]).toContain(heroMode);
      }

      // The mode switch and the keyword field work.
      const modes = page.locator("section#modes");
      await modes.getByRole("button", { name: /Auto/ }).click();
      await expect(modes.getByRole("button", { name: /Auto/ })).toHaveAttribute("aria-pressed", "true");
      await expect(modes.getByText("Sent by the AI").first()).toBeVisible();
      const keyword = page.getByRole("textbox", { name: "The keyword is yours" });
      await keyword.fill("guide");
      await expect(keyword).toHaveValue("GUIDE");
      await expect(page.locator("[data-kw-show]")).toHaveText("GUIDE");

      // Scroll through the whole page, as a visitor would.
      const height = await page.evaluate(() => document.documentElement.scrollHeight);
      for (let y = 0; y < height; y += 400) {
        await page.evaluate((top) => window.scrollTo(0, top), y);
        await page.waitForTimeout(80);
      }
      await page.waitForTimeout(500);

      // LP-1.1 (C-157): the AI draft keeps a transparent, block-level text box while it writes, so it
      // stays readable on the dark card (the DM's typing dots once shared its class).
      const draft = await page.locator(".ddraft-t").evaluate((el) => {
        const style = getComputedStyle(el);
        return { background: style.backgroundColor, display: style.display };
      });
      expect(draft).toEqual({ background: "rgba(0, 0, 0, 0)", display: "block" });

      // Sections in order (C-157): a night band every two or three sections, Security early, the
      // connections inside Features, the setup steps as the bridge into Pricing.
      const order = await page.$$eval("main > section", (sections) => sections.map((s) => s.id || s.getAttribute("aria-labelledby") || s.getAttribute("aria-label")));
      expect(order).toEqual([
        "hero-title",
        "how-it-works",
        "automations",
        "modes",
        "security",
        "who-its-for",
        "features",
        "setup",
        "pricing",
        "faq",
        "cta-title",
      ]);
      await expect(page.locator("section#features #integrations")).toHaveCount(1);
      // The FAQ shows 6 to 8 questions and links to the rest.
      const questions = await page.locator("section#faq details").count();
      expect(questions).toBeGreaterThanOrEqual(6);
      expect(questions).toBeLessThanOrEqual(8);
      await expect(page.locator("section#faq").getByRole("link", { name: "See all questions" })).toHaveAttribute("href", "/faq");

      // WCAG 2.2.2: nothing loops forever. The closer's inbox is still, and any infinite CSS animation
      // left on the page sits under a pause control.
      await expect(page.locator(".close .falling")).toHaveCount(0);
      // The closer (C-159 final CTA, C-161): one action, the email as a line of text, and the channel
      // line above the heading, hidden from assistive tech and drawn once (no loop).
      const closer = page.locator("section.close");
      await expect(closer.getByRole("link")).toHaveCount(2);
      await expect(closer.getByRole("link", { name: /Start free/ })).toHaveCount(1);
      await expect(closer.getByText(/Questions\? Write to/)).toBeVisible();
      await expect(closer.getByRole("link", { name: "support@amplychat.com" })).toHaveAttribute("href", "mailto:support@amplychat.com");
      await expect(closer.locator(".close-line[aria-hidden] i")).toHaveCount(3);
      const loose = await page.evaluate(() =>
        document
          .getAnimations()
          .filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations === Infinity)
          .filter((a) => !((a.effect as KeyframeEffect | null)?.target as Element | null)?.closest("[data-motion-scope]")).length,
      );
      expect(loose).toBe(0);

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
      expect(cls, `layout shift on / at ${name}`).toBeLessThanOrEqual(LIMIT);
    });
  }

  test("the comment scene has a pause control that stops it, and How it works pins on a wide screen (C-157)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
    // How it works: the heading is inside the pinned frame.
    await expect(page.locator("[data-decide-sticky] h2")).toHaveText("AI replies from your own knowledge");
    expect(await page.locator("[data-decide-sticky]").evaluate((el) => getComputedStyle(el).position)).toBe("sticky");
    // Wide screens scrub it with the scroll, so it has no pause control of its own.
    await expect(page.locator("section#how-it-works [data-motion-toggle]")).toBeHidden();

    const automations = page.locator("section#automations");
    await automations.scrollIntoViewIfNeeded();
    const toggle = automations.getByRole("button", { name: "Pause the example" });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(automations).toHaveAttribute("data-motion-paused", "");
    const count = await automations.locator("[data-comments] .cmt").allTextContents();
    await page.waitForTimeout(2_500);
    expect(await automations.locator("[data-comments] .cmt").allTextContents()).toEqual(count);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  test("the hero's scattered inbox sorts as the page scrolls, and the headline never moves (C-157 motion)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.addInitScript(() => {
      const w = window as unknown as { __cls: number };
      w.__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) if (!entry.hadRecentInput) w.__cls += entry.value;
      }).observe({ type: "layout-shift", buffered: true });
    });
    await page.goto("/");
    await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
    const scrub = page.locator("[data-hero-scrub]");
    const { range } = await scrub.evaluate((el: HTMLElement) => ({ range: el.offsetHeight - el.querySelector<HTMLElement>(".hero-sticky")!.offsetHeight }));
    // 170vh in all: a short scrub.
    expect(range).toBeGreaterThan(400);
    expect(range).toBeLessThan(900);
    const state = () =>
      page.evaluate(() => {
        const notes = [...document.querySelectorAll<HTMLElement>("[data-notes] .note")];
        const moved = notes.filter((n) => {
          const t = getComputedStyle(n).transform;
          return t !== "none" && t !== "matrix(1, 0, 0, 1, 0, 0)";
        }).length;
        return { moved, h1: Math.round(document.querySelector("h1")!.getBoundingClientRect().top) };
      });
    const at = async (fraction: number) => {
      await page.evaluate((y) => window.scrollTo(0, y), Math.round(fraction * range));
      await page.waitForTimeout(250);
      return state();
    };
    const start = await at(0);
    expect(start.moved).toBe(8); // scattered: every message out of its row
    const middle = await at(0.4);
    const end = await at(1);
    expect(end.moved).toBe(0); // sorted
    expect(middle.h1).toBe(start.h1); // the headline is pinned, not moved
    expect(end.h1).toBe(start.h1);
    expect(await page.evaluate(() => (window as unknown as { __cls: number }).__cls)).toBe(0);
  });

  test("on a tall wide screen the first screen is complete: copy and inbox at the top, the strip at its foot (C-157 hero spacing)", async ({ page }) => {
    for (const [width, height] of [
      [1920, 890],
      [1440, 900],
    ]) {
      await page.setViewportSize({ width, height });
      await page.goto("/");
      const geo = await page.evaluate(() => {
        const box = (s: string) => document.querySelector(s)!.getBoundingClientRect();
        const nav = document.querySelector("header")!.getBoundingClientRect().bottom;
        const top = Math.min(box(".hero-tag").top, box(".inbox").top);
        const content = Math.max(box(".hero-copy").bottom, box(".stage-cap").bottom);
        return { above: top - nav, below: box(".strip-in").top - content, stripBottom: box(".strip").bottom, vh: innerHeight, sideways: document.documentElement.scrollWidth > innerWidth };
      });
      expect(geo.above).toBeGreaterThan(16);
      expect(geo.above).toBeLessThan(110); // was about 170 when the content sat centred in the frame
      expect(geo.below).toBeGreaterThan(16); // the strip never runs into the inbox
      expect(Math.round(geo.stripBottom)).toBe(geo.vh); // its foot is the first screen's foot
      expect(geo.sideways).toBe(false);
    }
  });

  test("on a short wide screen the strip follows the pinned frame (C-157 hero spacing)", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    const stripTop = await page.locator(".strip").evaluate((el) => el.getBoundingClientRect().top);
    expect(stripTop).toBeGreaterThan(768);
  });

  test("on a phone the hero sorts by itself once, with a pause control that hides when it ends (C-157 motion)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/");
    await page.locator("[data-inbox]").scrollIntoViewIfNeeded();
    await expect(page.locator("[data-stage][data-play]")).toHaveCount(1, { timeout: 15_000 });
    // It ends sorted (about 1.2 s), and its pause control goes away with it.
    await expect
      .poll(
        () =>
          page.evaluate(
            () =>
              [...document.querySelectorAll<HTMLElement>("[data-notes] .note")].filter((n) => {
                const t = getComputedStyle(n).transform;
                return t !== "none" && t !== "matrix(1, 0, 0, 1, 0, 0)";
              }).length,
          ),
        { timeout: 5_000 },
      )
      .toBe(0);
    await expect(page.locator(".hero [data-motion-toggle]")).toBeHidden();
  });

  test("with reduced motion the hero is the sorted inbox, still, and the FAQ toggles at once (C-157 motion)", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    expect(await page.locator(".hero-sticky").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
    expect(await page.locator("[data-notes] .note").first().evaluate((el) => getComputedStyle(el).transform)).toBe("none");
    const item = page.locator("section#faq details.qa").nth(1);
    await item.scrollIntoViewIfNeeded();
    await item.locator("summary").click();
    await expect(item).toHaveAttribute("open", "");
  });

  test("the landing's FAQ opens and closes on click and from the keyboard (C-157 motion)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const item = page.locator("section#faq details.qa").nth(1);
    await item.scrollIntoViewIfNeeded();
    const summary = item.locator("summary");
    await summary.click();
    await expect(item).toHaveAttribute("open", "");
    await expect(item.locator("p")).toBeVisible();
    await summary.click();
    await expect(item).not.toHaveAttribute("open", "");
    await expect.poll(() => item.evaluate((el) => Math.round(el.getBoundingClientRect().height - el.querySelector("summary")!.getBoundingClientRect().height))).toBeLessThanOrEqual(1);
    await summary.focus();
    await page.keyboard.press("Enter");
    await expect(item).toHaveAttribute("open", "");
    await page.keyboard.press("Space");
    await expect(item).not.toHaveAttribute("open", "");
  });

  test("the organized sections line up: equal panels and cards, aligned statuses, sticky heads (C-157 organize)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    // The bands below How it works render as they near the viewport; bring each one in before measuring.
    const bring = async (selector: string) => {
      await page.locator(selector).first().scrollIntoViewIfNeeded();
      await page.waitForTimeout(150);
    };
    const bottoms = (selector: string) =>
      page.$$eval(selector, (els) => els.map((el) => Math.round(el.getBoundingClientRect().bottom)));
    const tops = (selector: string) => page.$$eval(selector, (els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
    const same = (values: number[]) => Math.max(...values) - Math.min(...values) <= 1;

    // Automations: the Reel, the automation and the DM end on one line.
    await bring("section#automations .machine");
    expect(same(await bottoms("section#automations .machine > :is(.post, .rule, .dm)"))).toBe(true);

    // Security: a spec list of five rows; the heading block stays in view while the rows scroll.
    await bring("section#security");
    await expect(page.locator("section#security .spec-row")).toHaveCount(5);
    await page.evaluate(() => window.scrollTo(0, document.querySelector("#security")!.getBoundingClientRect().top + window.scrollY + 160));
    const headTop = await page.locator("section#security .spec-head").evaluate((el) => el.getBoundingClientRect().top);
    expect(headTop).toBeGreaterThan(0);

    // Features: three groups of cards, with no half-empty row.
    await bring("section#features .fgroup");
    await expect(page.locator("section#features .fgroup")).toHaveCount(3);
    await expect(page.locator("section#features .more-links")).toHaveCount(1);

    // Integrations: four cards a row, equal heights and every status on one line per row.
    await bring("#integrations .chan");
    const cards = await page.$$eval("#integrations .crow", (els) =>
      els.map((el) => ({ top: Math.round(el.getBoundingClientRect().top), height: Math.round(el.getBoundingClientRect().height), status: Math.round(el.querySelector(".st")!.getBoundingClientRect().top) })),
    );
    expect(cards).toHaveLength(8);
    for (const row of [cards.slice(0, 4), cards.slice(4)]) {
      expect(same(row.map((c) => c.top))).toBe(true);
      expect(same(row.map((c) => c.height))).toBe(true);
      expect(same(row.map((c) => c.status))).toBe(true);
    }

    // Pricing: plan cards of one height, with their buttons and lists starting at one height.
    await bring("section#pricing .plans");
    expect(same(await bottoms("section#pricing .plan"))).toBe(true);
    expect(same(await tops("section#pricing .plan > .btn"))).toBe(true);
    expect(same(await tops("section#pricing .plan > .limits"))).toBe(true);

    // FAQ: the heading block stays in view beside the long list.
    await bring("section#faq");
    await page.evaluate(() => window.scrollTo(0, document.querySelector("#faq")!.getBoundingClientRect().top + window.scrollY + 240));
    const faqHead = await page.locator("section#faq .faq-head").evaluate((el) => el.getBoundingClientRect().top);
    expect(faqHead).toBeGreaterThan(0);
  });

  test("on a phone How it works plays once by itself, with a pause control", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/");
    await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
    const how = page.locator("section#how-it-works");
    await how.locator("[data-kb]").scrollIntoViewIfNeeded();
    const toggle = how.getByRole("button", { name: "Pause the example" });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(how).toHaveAttribute("data-motion-paused", "");
  });
});

test.describe("all questions page", () => {
  test("/faq lists every question, the landing ones included, with matching FAQPage JSON-LD", async ({ page }) => {
    await page.goto("/faq");
    await expect(page.getByRole("heading", { level: 1, name: "Common questions" })).toBeVisible();
    const questions = await page.locator("main details summary h3").allTextContents();
    expect(questions.length).toBeGreaterThan(8);
    const data = await page.$$eval('script[type="application/ld+json"]', (scripts) => scripts.map((s) => JSON.parse(s.textContent ?? "null")));
    const faq = data.find((node) => node["@type"] === "FAQPage");
    expect(faq.mainEntity.map((entity: { name: string }) => entity.name)).toEqual(questions);
    expect(data.some((node) => node["@type"] === "BreadcrumbList")).toBe(true);
    // The first question opens, and closes again (the height animates both ways, C-157 motion).
    await page.locator("main details summary").first().click();
    await expect(page.locator("main details").first()).toHaveAttribute("open", "");
    await page.locator("main details summary").first().click();
    await expect(page.locator("main details").first()).not.toHaveAttribute("open", "");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
