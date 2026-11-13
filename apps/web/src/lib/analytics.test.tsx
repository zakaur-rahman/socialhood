import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CtaLink } from "@/components/marketing/primitives";
import { PRO_SIGN_UP_PATH } from "@/lib/resolve";

import { START_FREE_EVENT, UMAMI_DOMAINS, ctaEvent } from "./analytics";

describe("landing-page analytics (C-194)", () => {
  it("counts every link into sign-up as a Start free click, and nothing else", () => {
    expect(ctaEvent("https://dashboard.amplychat.com/sign-up")).toBe(START_FREE_EVENT);
    expect(ctaEvent(`https://dashboard.amplychat.com${PRO_SIGN_UP_PATH}`)).toBe(START_FREE_EVENT);
    expect(ctaEvent("/sign-up")).toBe(START_FREE_EVENT);
    expect(ctaEvent("/how-it-works")).toBeUndefined();
    expect(ctaEvent("/sign-up-guide")).toBeUndefined();
    expect(ctaEvent("mailto:support@amplychat.com")).toBeUndefined();
  });

  it("tags the button, so Umami counts the click with the page it was on", () => {
    render(
      <>
        <CtaLink href="https://dashboard.amplychat.com/sign-up">Start free</CtaLink>
        <CtaLink href="/how-it-works">See how it works</CtaLink>
      </>,
    );
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("data-umami-event", START_FREE_EVENT);
    expect(screen.getByRole("link", { name: "See how it works" })).not.toHaveAttribute("data-umami-event");
  });

  it("counts only on the public site's host: the dashboard, local runs and CI send nothing", () => {
    expect(UMAMI_DOMAINS).toBe("amplychat.com");
  });
});
