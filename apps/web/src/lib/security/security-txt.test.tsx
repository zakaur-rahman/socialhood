import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SecurityPage, { metadata } from "@/app/(marketing)/security/page";
import { GET, revalidate } from "@/app/.well-known/security.txt/route";

import { SECURITY_TXT_LIFETIME_DAYS, securityTxt } from "./security-txt";

// C-143: /.well-known/security.txt (RFC 9116) and the /security policy page it points at.

function fields(text: string): Record<string, string> {
  return Object.fromEntries(
    text
      .trim()
      .split("\n")
      .map((line) => {
        const at = line.indexOf(": ");
        return [line.slice(0, at), line.slice(at + 2)];
      }),
  );
}

describe("security.txt", () => {
  const now = new Date("2026-10-26T15:30:00Z");
  const txt = securityTxt(now, "https://amplychat.com");

  it("names the contact, language, canonical address and policy", () => {
    expect(fields(txt)).toMatchObject({
      Contact: "mailto:support@amplychat.com",
      "Preferred-Languages": "en",
      Canonical: "https://amplychat.com/.well-known/security.txt",
      Policy: "https://amplychat.com/security",
    });
  });

  it("expires just under a year out, as an RFC 3339 UTC time", () => {
    const expires = fields(txt).Expires;
    expect(expires).toMatch(/^\d{4}-\d{2}-\d{2}T00:00:00Z$/);
    const days = (Date.parse(expires) - now.getTime()) / 86_400_000;
    expect(days).toBeGreaterThan(SECURITY_TXT_LIFETIME_DAYS - 1);
    expect(days).toBeLessThan(365);
  });

  it("has only the fields RFC 9116 defines, one per line, and ends with a newline", () => {
    const allowed = ["Contact", "Expires", "Preferred-Languages", "Canonical", "Policy"];
    expect(Object.keys(fields(txt)).every((name) => allowed.includes(name))).toBe(true);
    expect(txt.endsWith("\n")).toBe(true);
    expect(txt.match(/^Expires:/gm)).toHaveLength(1);
  });

  it("is served as UTF-8 plain text and rebuilt daily", async () => {
    const response = GET();
    expect(response.headers.get("Content-Type")).toBe("text/plain; charset=utf-8");
    expect(await response.text()).toContain("Contact: mailto:support@amplychat.com");
    expect(revalidate).toBe(86400);
  });
});

describe("the /security page", () => {
  it("has its canonical metadata", () => {
    expect(metadata.title).toBe("Security");
    expect(metadata.alternates?.canonical).toBe("/security");
  });

  it("says how to report, what is in scope, and promises no bounty", () => {
    render(<SecurityPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Security" })).toBeInTheDocument();
    for (const name of ["How to report a problem", "What is in scope", "What is out of scope", "Testing rules"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    const mail = screen.getAllByRole("link", { name: "support@amplychat.com" })[0];
    expect(mail.getAttribute("href")).toMatch(/^mailto:support@amplychat\.com/);
    expect(screen.getByText(/don.t run a paid bug bounty/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "security.txt" })).toHaveAttribute("href", "/.well-known/security.txt");
  });
});
