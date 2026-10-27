import { describe, expect, it } from "vitest";

import { signedInHint } from "./session-hint";

describe("the signed-in hint from Clerk's cookie (C-148)", () => {
  it("is signed in when __client_uat, plain or suffixed, is after 0", () => {
    expect(signedInHint("__client_uat=1761550000")).toBe(true);
    expect(signedInHint("sh_theme=dark; __client_uat_Ab1-x_Y=1761550000")).toBe(true);
  });

  it("is signed out after sign-out (0), without the cookie, or with junk", () => {
    expect(signedInHint("")).toBe(false);
    expect(signedInHint("__client_uat=0")).toBe(false);
    expect(signedInHint("sh_theme=dark; __client_uat_Ab1=0")).toBe(false);
    expect(signedInHint("__client_uat=abc")).toBe(false);
    expect(signedInHint("x__client_uat=17; __session=eyJ")).toBe(false);
  });
});
