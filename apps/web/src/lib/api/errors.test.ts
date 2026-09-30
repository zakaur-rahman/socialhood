import { describe, expect, it } from "vitest";

import { ApiError, isPlanLimitError, toApiError } from "./errors";

describe("402 problems (C-049)", () => {
  it("keep the entitlement key and the limit", () => {
    const error = toApiError({
      type: "t",
      title: "Payment required",
      status: 402,
      code: "quota_exceeded",
      detail: "Your plan includes 3 active automations.",
      entitlement: "active_automations",
      limit: 3,
    });
    expect(error.entitlement).toBe("active_automations");
    expect(error.limit).toBe(3);
    expect(isPlanLimitError(error)).toBe(true);
  });

  it("a missing feature has a null limit", () => {
    const error = toApiError({ type: "t", title: "t", status: 402, code: "entitlement_required", entitlement: "ai_modes", limit: null });
    expect(error.limit).toBeNull();
    expect(isPlanLimitError(error)).toBe(true);
  });

  it("other errors are not plan limits", () => {
    expect(isPlanLimitError(toApiError({ type: "t", title: "t", status: 409, code: "conflict" }))).toBe(false);
    expect(isPlanLimitError(new Error("402"))).toBe(false);
    expect(toApiError({ type: "t", title: "t", status: 404, code: "not_found" }).entitlement).toBeUndefined();
  });
});

describe("toApiError", () => {
  it("keeps the code, detail, field errors and request id of a problem body", () => {
    const error = toApiError({
      type: "https://api.socialhood.com/errors/validation_error",
      title: "The request is not valid",
      status: 422,
      code: "validation_error",
      detail: "Check the fields",
      errors: [{ field: "text", message: "too long" }],
      request_id: "01M3M515PZ1EF4CTKT8QW6R1F0",
    });
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe("validation_error");
    expect(error.message).toBe("Check the fields");
    expect(error.errors).toEqual([{ field: "text", message: "too long" }]);
    expect(error.requestId).toBe("01M3M515PZ1EF4CTKT8QW6R1F0");
  });

  it("treats a failure without a problem body as a network error", () => {
    expect(toApiError(new TypeError("Failed to fetch")).code).toBe("network");
    expect(toApiError("<html>502</html>", 502).code).toBe("internal");
  });

  it("returns an existing ApiError unchanged", () => {
    const original = toApiError({ type: "t", title: "Nope", status: 404, code: "not_found" });
    expect(toApiError(original)).toBe(original);
  });
});
