import { describe, expect, it } from "vitest";

import {
  charCount,
  clampChars,
  insertAt,
  renderFields,
  utf8Bytes,
  withDisclosure,
  worstCaseBytes,
  worstCaseChars,
} from "./render";

describe("renderFields (FR-AUT-13), as the API renders", () => {
  it("fills known fields", () => {
    expect(renderFields("Hi {first_name}! @{username}", { first_name: "Priya", username: "priya.styles" })).toBe(
      "Hi Priya! @priya.styles",
    );
  });

  it("uses the fallback, or 'there' for a first name, never the literal field", () => {
    expect(renderFields("Hi {first_name|friend}!", { first_name: null })).toBe("Hi friend!");
    expect(renderFields("Hi {first_name}!", {})).toBe("Hi there!");
    expect(renderFields("by {username}", { username: "" })).toBe("by ");
  });

  it("leaves unknown braces alone", () => {
    expect(renderFields("{price} {first_name}", { first_name: "Priya" })).toBe("{price} Priya");
  });
});

describe("byte counter (TR-PL-10)", () => {
  it("counts UTF-8 bytes", () => {
    expect(utf8Bytes("abc")).toBe(3);
    expect(utf8Bytes("नमस्ते")).toBe(18);
    expect(utf8Bytes("😍")).toBe(4);
  });

  it("counts each field at its longest and the disclosure line", () => {
    // 30 bytes for the name sample + "Hi !" (4)
    expect(worstCaseBytes("Hi {first_name}!", null)).toBe(34);
    // A fallback longer than the sample counts instead.
    const long = "a".repeat(40);
    expect(worstCaseBytes(`{first_name|${long}}`, null)).toBe(40);
    // "\n\n" + "Sent automatically" (18)
    expect(worstCaseBytes("Hi", "Sent automatically")).toBe(2 + 2 + 18);
    expect(withDisclosure("Hi", "Sent automatically")).toBe("Hi\n\nSent automatically");
  });

  it("counts characters as the API does, for the button template's 640", () => {
    expect(worstCaseChars("Hi {first_name}!", null)).toBe(34);
    // Code points, not UTF-16 units: an emoji is one character, Devanagari one per code point.
    expect(worstCaseChars("😍", null)).toBe(1);
    expect(worstCaseChars("नमस्ते", "Sent automatically")).toBe(6 + 2 + 18);
  });
});

describe("character limits (FR-AUT-21, FR-AUT-22)", () => {
  it("counts and cuts by code points, as the API does", () => {
    expect(charCount("Follow us 💛")).toBe(11);
    expect(clampChars("Send me the link now please", 20)).toBe("Send me the link now");
    expect(clampChars("💛".repeat(21), 20)).toBe("💛".repeat(20));
    expect(clampChars("Short", 20)).toBe("Short");
  });
});

describe("insertAt", () => {
  it("replaces the selection and returns the caret after the token", () => {
    expect(insertAt("Hi !", "{first_name}", 3)).toEqual({ text: "Hi {first_name}!", caret: 15 });
    expect(insertAt("Hi you!", "{username}", 3, 6)).toEqual({ text: "Hi {username}!", caret: 13 });
  });
});
