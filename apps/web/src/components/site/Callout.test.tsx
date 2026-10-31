import { render, screen } from "@testing-library/react";
import { Wallet } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Callout } from "./Callout";

describe("callouts (C-159)", () => {
  it("name their kind, or the given title", () => {
    render(
      <>
        <Callout tone="tip">
          <p>A</p>
        </Callout>
        <Callout tone="means">
          <p>B</p>
        </Callout>
        <Callout title="Two mistakes to avoid">
          <p>C</p>
        </Callout>
      </>,
    );
    expect(screen.getByRole("complementary", { name: "Tip" })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "What this means for you" })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Two mistakes to avoid" })).toBeTruthy();
  });

  it("the info tone shows its own icon and no title unless given, and the AI moment is marked", () => {
    const { container } = render(
      <>
        <Callout tone="info" icon={Wallet}>
          <p>Meta charges are separate.</p>
        </Callout>
        <Callout tone="info" title="Grievances" ai>
          <p>Write to us.</p>
        </Callout>
      </>,
    );
    const [plain, titled] = container.querySelectorAll(".callout");
    expect(plain).toHaveClass("callout", "callout-info");
    expect(plain.querySelector(".callout-t")).toBeNull();
    expect(plain.querySelector(".callout-ico svg")).toHaveClass("lucide-wallet");
    expect(plain).toHaveTextContent("Meta charges are separate.");
    expect(titled.querySelector(".callout-t")).toHaveTextContent("Grievances");
    expect(titled).toHaveClass("callout-ai");
    expect(screen.getByRole("complementary", { name: "Grievances" })).toBeTruthy();
  });
});
