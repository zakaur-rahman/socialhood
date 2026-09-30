import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiProvider } from "./provider";

const auth = vi.hoisted(() => ({
  state: { isLoaded: true, isSignedIn: false as boolean | undefined, getToken: async () => null as string | null },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth.state }));

function renderArea() {
  return render(
    <ApiProvider fallback={<p>Loading</p>}>
      <p>Signed-in area</p>
    </ApiProvider>,
  );
}

beforeEach(() => {
  auth.state = { isLoaded: true, isSignedIn: false, getToken: async () => null };
});

describe("ApiProvider (F-01)", () => {
  it("holds the signed-in area until Clerk has the session, so no request goes out without a token", () => {
    // Right after sign-up, Clerk has navigated to /app but not set the new session yet.
    const view = renderArea();
    expect(screen.getByText("Loading")).toBeInTheDocument();
    expect(screen.queryByText("Signed-in area")).not.toBeInTheDocument();

    auth.state = { isLoaded: true, isSignedIn: true, getToken: async () => "token" };
    view.rerender(
      <ApiProvider fallback={<p>Loading</p>}>
        <p>Signed-in area</p>
      </ApiProvider>,
    );
    expect(screen.getByText("Signed-in area")).toBeInTheDocument();
    expect(screen.queryByText("Loading")).not.toBeInTheDocument();
  });

  it("holds it while Clerk is still loading", () => {
    auth.state = { isLoaded: false, isSignedIn: undefined, getToken: async () => null };
    renderArea();
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("renders it straight away for a signed-in user", () => {
    auth.state = { isLoaded: true, isSignedIn: true, getToken: async () => "token" };
    renderArea();
    expect(screen.getByText("Signed-in area")).toBeInTheDocument();
  });
});
