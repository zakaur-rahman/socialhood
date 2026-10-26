import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@clerk/nextjs", () => ({
  SignOutButton: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { PrelaunchNotice } from "./PrelaunchNotice";

describe("PrelaunchNotice (website-only deploy, C-145)", () => {
  it("says the account is ready and the app opens soon, with a way back and out", () => {
    render(<PrelaunchNotice />);
    expect(screen.getByRole("heading", { level: 1, name: "Your account is ready" })).toBeInTheDocument();
    expect(screen.getByText(/Amplychat opens soon/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "support@amplychat.com" })).toHaveAttribute(
      "href",
      "mailto:support@amplychat.com",
    );
    expect(screen.getByRole("link", { name: "Back to the website" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
