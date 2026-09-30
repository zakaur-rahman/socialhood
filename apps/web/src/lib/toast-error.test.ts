import { beforeEach, describe, expect, it, vi } from "vitest";

import { toApiError } from "@/lib/api/errors";

import { toastError } from "./toast-error";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

beforeEach(() => toast.error.mockReset());

describe("toastError: one message per failure (T8.4)", () => {
  it("a plan limit (402) is left to the upgrade dialog", () => {
    toastError(toApiError({ type: "t", title: "t", status: 402, code: "quota_exceeded", detail: "Your plan includes 3." }));
    toastError(toApiError({ type: "t", title: "t", status: 402, code: "entitlement_required" }));
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("anything else is a toast, with the screen's own words when given", () => {
    const conflict = toApiError({ type: "t", title: "t", status: 409, code: "conflict", detail: "Publishing started." });
    toastError(conflict);
    toastError(conflict, "This post can't be moved now.");
    expect(toast.error.mock.calls).toEqual([["Publishing started."], ["This post can't be moved now."]]);
  });
});
