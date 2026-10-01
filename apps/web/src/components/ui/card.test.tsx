import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CARD_TITLE } from "@/styles/tokens";

import { Card, CardAction, CardBleed, CardDescription, CardHeader, CardInset, CardTitle } from "./card";

const slot = (name: string) => document.querySelector(`[data-slot="${name}"]`) as HTMLElement;
const classList = (el: HTMLElement) => [...el.classList];

describe("Card (UI-020)", () => {
  it("is a flat panel with a line edge and the xl radius (D-02), standard padding by default", () => {
    render(<Card>Replies this week</Card>);
    const card = slot("card");
    expect(card).toHaveClass("rounded-xl", "border", "border-line", "bg-panel", "p-(--card-padding)");
    expect(card).toHaveAttribute("data-padding", "standard");
    expect(card).toHaveAttribute("data-tone", "default");
    // standard: 16 px, through the variable the card pads with
    expect(card).toHaveClass("[--card-padding:--spacing(4)]");
    expect(classList(card).some((c) => /^shadow|^rounded-2xl$|^p-\d|^md:p-/.test(c))).toBe(false);
  });

  it("pads 20 px on phones and 24 px from md when roomy", () => {
    render(<Card padding="roomy">Plan</Card>);
    const card = slot("card");
    expect(card).toHaveAttribute("data-padding", "roomy");
    expect(card).toHaveClass("p-(--card-padding)", "[--card-padding:--spacing(5)]", "md:[--card-padding:--spacing(6)]");
    expect(card).not.toHaveClass("[--card-padding:--spacing(4)]");
  });

  it("marks the danger tone with a 2 px danger leading edge and keeps the line edge elsewhere", () => {
    render(<Card tone="danger">Delete workspace</Card>);
    const card = slot("card");
    expect(card).toHaveAttribute("data-tone", "danger");
    expect(card).toHaveClass("border", "border-line", "border-l-2", "border-l-danger", "bg-panel");
  });

  it("gives the brand tone a brand-line edge in place of the line edge", () => {
    render(<Card tone="brand">Pro</Card>);
    const card = slot("card");
    expect(card).toHaveAttribute("data-tone", "brand");
    expect(card).toHaveClass("border", "border-brand-line", "bg-panel");
    expect(card).not.toHaveClass("border-line");
    expect(card).not.toHaveClass("border-l-2");
  });

  it("adds no edge for the default tone", () => {
    render(<Card>Default</Card>);
    expect(classList(slot("card")).filter((c) => c.startsWith("border-l-"))).toEqual([]);
  });

  it("renders as its child with asChild: a section named by its title", () => {
    render(
      <Card asChild padding="roomy" className="space-y-4">
        <section aria-labelledby="payments-title">
          <CardHeader>
            <CardTitle id="payments-title">Payment history</CardTitle>
          </CardHeader>
        </section>
      </Card>,
    );
    const region = screen.getByRole("region", { name: "Payment history" });
    expect(region.tagName).toBe("SECTION");
    expect(region).toHaveAttribute("data-slot", "card");
    expect(region).toHaveClass("rounded-xl", "bg-panel", "space-y-4", "[--card-padding:--spacing(5)]");
  });
});

describe("CardHeader (UI-020)", () => {
  it("titles the card with a 16 px semibold h2, and an h3 through asChild", () => {
    render(
      <>
        <Card>
          <CardHeader>
            <CardTitle>Top posts</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle asChild>
              <h3>Top intents</h3>
            </CardTitle>
          </CardHeader>
        </Card>
      </>,
    );
    const h2 = screen.getByRole("heading", { level: 2, name: "Top posts" });
    expect(h2).toHaveClass(...CARD_TITLE.split(" "));
    expect(CARD_TITLE).toBe("text-base font-semibold");
    const h3 = screen.getByRole("heading", { level: 3, name: "Top intents" });
    expect(h3).toHaveClass("text-base", "font-semibold");
    expect(h3).toHaveAttribute("data-slot", "card-title");
  });

  it("sizes the description from the card: 12 px in a standard card, 14 px in a roomy one", () => {
    render(
      <Card padding="roomy">
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>Choose what reaches you.</CardDescription>
        </CardHeader>
      </Card>,
    );
    const description = screen.getByText("Choose what reaches you.");
    expect(description.tagName).toBe("P");
    expect(description).toHaveClass("text-xs", "text-fg-secondary", "group-data-[padding=roomy]/card:text-sm");
    // The roomy size keys off the card's data-padding, which the card sets.
    expect(description.closest("[data-slot=card]")).toHaveAttribute("data-padding", "roomy");
    expect(slot("card")).toHaveClass("group/card");
  });

  it("puts the action at the top right, beside the title and description", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Knowledge</CardTitle>
          <CardDescription>4 sources</CardDescription>
          <CardAction>
            <button type="button">Add source</button>
          </CardAction>
        </CardHeader>
      </Card>,
    );
    expect(slot("card-header")).toHaveClass("grid", "has-data-[slot=card-action]:grid-cols-[minmax(0,1fr)_auto]", "gap-x-3", "gap-y-1");
    const action = slot("card-action");
    expect(action).toHaveClass("col-start-2", "row-start-1", "row-span-2", "justify-self-end");
    expect(action).toContainElement(screen.getByRole("button", { name: "Add source" }));
  });
});

describe("CardInset (UI-020)", () => {
  it("is a rounded-lg group with a line edge: 16 px for form groups, 12 px for rows", () => {
    render(
      <Card>
        <CardInset data-testid="standard">Form group</CardInset>
        <CardInset data-testid="compact" padding="compact">
          Rows
        </CardInset>
      </Card>,
    );
    const standard = screen.getByTestId("standard");
    expect(standard).toHaveClass("rounded-lg", "border", "border-line", "p-(--card-padding)", "[--card-padding:--spacing(4)]");
    expect(standard).toHaveAttribute("data-slot", "card-inset");
    const compact = screen.getByTestId("compact");
    expect(compact).toHaveClass("rounded-lg", "[--card-padding:--spacing(3)]");
    expect(compact).not.toHaveClass("[--card-padding:--spacing(4)]");
  });
});

describe("CardBleed (UI-020)", () => {
  it("spans the card's padding through --card-padding, without a negative margin", () => {
    render(
      <Card padding="roomy">
        <CardBleed>
          <table>
            <tbody>
              <tr>
                <td>1 Oct</td>
              </tr>
            </tbody>
          </table>
        </CardBleed>
      </Card>,
    );
    const bleed = slot("card-bleed");
    expect(bleed).toHaveClass("relative", "-start-(--card-padding)", "w-[calc(100%+2*var(--card-padding))]");
    expect(classList(bleed).some((c) => /(^|:)-m[xlrse]?-/.test(c))).toBe(false);
  });
});
