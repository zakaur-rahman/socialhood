import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { clampWidth, usePaneWidth } from "./use-pane-width";

const LIMITS = { fallback: 320, min: 260, max: 560 };

afterEach(() => window.localStorage.clear());

describe("usePaneWidth (UI-078)", () => {
  it("starts at the fallback and remembers a new width per device", () => {
    const { result } = renderHook(() => usePaneWidth("test-a", LIMITS));
    expect(result.current[0]).toBe(320);
    act(() => result.current[1](400));
    expect(result.current[0]).toBe(400);
    expect(window.localStorage.getItem("socialhood:pane-width:test-a")).toBe("400");
  });

  it("clamps what it stores and what it reads", () => {
    window.localStorage.setItem("socialhood:pane-width:test-b", "9999");
    const { result } = renderHook(() => usePaneWidth("test-b", LIMITS));
    expect(result.current[0]).toBe(560);
    act(() => result.current[1](10));
    expect(result.current[0]).toBe(260);
  });

  it("ignores a stored value that is not a number, and reset goes back to the fallback", () => {
    window.localStorage.setItem("socialhood:pane-width:test-c", "wide");
    const { result } = renderHook(() => usePaneWidth("test-c", LIMITS));
    expect(result.current[0]).toBe(320);
    act(() => result.current[1](480));
    act(() => result.current[2]());
    expect(result.current[0]).toBe(320);
  });

  it("clampWidth rounds and keeps a value inside the limits", () => {
    expect(clampWidth(300.6, LIMITS)).toBe(301);
    expect(clampWidth(100, LIMITS)).toBe(260);
    expect(clampWidth(900, LIMITS)).toBe(560);
  });
});
