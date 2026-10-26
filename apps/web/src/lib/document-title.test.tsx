import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useDocumentTitle } from "./document-title";

function Title({ title }: { title: string | null | undefined }) {
  useDocumentTitle(title);
  return null;
}

describe("useDocumentTitle (WCAG 2.4.2)", () => {
  afterEach(() => {
    document.title = "";
  });

  it("sets the title with the product suffix", () => {
    render(<Title title="Priya Nair" />);
    expect(document.title).toBe("Priya Nair · Amplychat");
  });

  it("follows the data as it arrives", () => {
    const { rerender } = render(<Title title="Comments" />);
    rerender(<Title title="Comments · Reel from 12 Sep" />);
    expect(document.title).toBe("Comments · Reel from 12 Sep · Amplychat");
  });

  it("leaves the title alone while the data is still loading", () => {
    document.title = "Inbox · Amplychat";
    render(<Title title={undefined} />);
    expect(document.title).toBe("Inbox · Amplychat");
  });
});
