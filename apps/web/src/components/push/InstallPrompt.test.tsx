import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetInstallPrompt } from "@/lib/push/install";
import * as support from "@/lib/push/support";

import { InstallPrompt } from "./InstallPrompt";

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1";

function fireInstallPrompt(outcome: "accepted" | "dismissed" = "accepted") {
  const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
    prompt: vi.fn(async () => {}),
    userChoice: Promise.resolve({ outcome }),
  });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
}

// Remembered flags also live in memory for the page's life, so each test gets its own key.
let storageKey = "test:install:0";

function renderPrompt(props: Partial<Parameters<typeof InstallPrompt>[0]> = {}) {
  return render(
    <InstallPrompt storageKey={storageKey} title="Install Social Hood" body="Open it like an app." {...props} />,
  );
}

let run = 0;

beforeEach(() => {
  run += 1;
  storageKey = `test:install:${run}`;
  window.localStorage.clear();
  resetInstallPrompt();
  // A browser tab on a computer (the test setup's matchMedia matches everything, standalone too).
  vi.spyOn(support, "readEnvironment").mockReturnValue({
    platform: "desktop",
    standalone: false,
    pushApis: true,
    permission: "default",
  });
});

afterEach(() => vi.restoreAllMocks());

describe("InstallPrompt (FR-NOT-03)", () => {
  it("nothing to offer: no card", () => {
    renderPrompt();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("where the browser can install: Install shows its prompt, and the mini-infobar is held back", async () => {
    const user = userEvent.setup();
    renderPrompt();
    const event = fireInstallPrompt();
    expect(event.defaultPrevented).toBe(true);
    await user.click(await screen.findByRole("button", { name: "Install app" }));
    expect(event.prompt).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByRole("status", { name: "Install Social Hood" })).not.toBeInTheDocument());
  });

  it("dismissed stays dismissed", async () => {
    const user = userEvent.setup();
    const first = renderPrompt();
    fireInstallPrompt();
    await user.click(await screen.findByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    first.unmount();
    renderPrompt();
    fireInstallPrompt();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("on iPhone: the Add to Home Screen steps; not once installed", () => {
    vi.spyOn(support, "readEnvironment").mockReturnValue({
      platform: "ios",
      standalone: false,
      pushApis: false,
      permission: "unsupported",
    });
    const first = renderPrompt();
    expect(screen.getByRole("list", { name: "Add Social Hood to your Home Screen" })).toBeInTheDocument();
    first.unmount();

    vi.spyOn(support, "readEnvironment").mockReturnValue({
      platform: "ios",
      standalone: true,
      pushApis: true,
      permission: "default",
    });
    const second = renderPrompt();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    second.unmount();
    // With an action (F-19's Turn on alerts) the card still shows, without the steps.
    renderPrompt({ always: true, action: <button type="button">Turn on alerts</button> });
    expect(screen.getByRole("status", { name: "Install Social Hood" })).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("detects an iPhone from its user agent", () => {
    expect(support.detectPlatform({ userAgent: IPHONE })).toBe("ios");
  });

  it("with always, the action shows even where installing isn't possible", () => {
    renderPrompt({ always: true, action: <button type="button">Turn on alerts</button> });
    expect(screen.getByRole("button", { name: "Turn on alerts" })).toBeInTheDocument();
  });
});
