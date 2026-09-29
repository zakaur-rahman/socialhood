import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RECONNECTING_GRACE_MS, setRealtimeStatus, useReconnecting, useRealtimeStore } from "./status";

describe("useReconnecting (the sidebar's notice)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useRealtimeStore.setState({ status: "connecting", since: 0 });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("is false while connecting or connected, and for a drop shorter than the grace period", () => {
    const { result } = renderHook(() => useReconnecting());
    expect(result.current).toBe(false);
    act(() => setRealtimeStatus("connected"));
    act(() => setRealtimeStatus("reconnecting"));
    act(() => vi.advanceTimersByTime(RECONNECTING_GRACE_MS - 100));
    expect(result.current).toBe(false);
    act(() => setRealtimeStatus("connected"));
    act(() => vi.advanceTimersByTime(RECONNECTING_GRACE_MS));
    expect(result.current).toBe(false);
  });

  it("turns true once a drop outlasts the grace period, and false when the stream opens again", () => {
    const { result } = renderHook(() => useReconnecting());
    act(() => setRealtimeStatus("reconnecting"));
    // Failed attempts during the same drop keep its start time.
    act(() => vi.advanceTimersByTime(2_000));
    act(() => setRealtimeStatus("reconnecting"));
    act(() => vi.advanceTimersByTime(RECONNECTING_GRACE_MS - 2_000));
    expect(result.current).toBe(true);
    act(() => setRealtimeStatus("connected"));
    expect(result.current).toBe(false);
    // A new drop waits its own grace period.
    act(() => setRealtimeStatus("reconnecting"));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(RECONNECTING_GRACE_MS));
    expect(result.current).toBe(true);
  });
});
