import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { message } from "@/test/api";

import { DateSeparator } from "./DateSeparator";
import { buildRows, MessageLog } from "./MessageLog";

const now = new Date("2026-09-28T12:00:00Z");
const tz = "Asia/Kolkata";

describe("DateSeparator (UX-INB-06)", () => {
  it.each([
    ["2026-09-28T05:00:00Z", "Today"],
    ["2026-09-27T05:00:00Z", "Yesterday"],
    ["2026-03-02T05:00:00Z", "Mon 2 Mar"],
    ["2025-03-03T05:00:00Z", "3 Mar 2025"],
  ])("%s → %s", (at, label) => {
    render(<DateSeparator at={at} timeZone={tz} now={now} />);
    expect(screen.getByRole("separator")).toHaveTextContent(label);
  });
});

describe("buildRows: separators and groups", () => {
  it("separates days and groups same-side bubbles within 5 minutes", () => {
    const rows = buildRows(
      [
        message({ id: "a", occurred_at: "2026-09-27T12:00:00Z" }),
        message({ id: "b", occurred_at: "2026-09-28T09:00:00Z" }),
        message({ id: "c", occurred_at: "2026-09-28T09:03:00Z" }),
        message({ id: "d", occurred_at: "2026-09-28T09:20:00Z" }),
        message({ id: "e", direction: "outbound", source: "human", occurred_at: "2026-09-28T09:21:00Z" }),
      ],
      tz,
    );
    expect(rows.map((r) => (r.type === "date" ? `[${r.key}]` : r.key))).toEqual([
      "[date-2026-09-27]",
      "a",
      "[date-2026-09-28]",
      "b",
      "c",
      "d",
      "e",
    ]);
    const flags = Object.fromEntries(
      rows.flatMap((r) => (r.type === "message" ? [[r.key, [r.groupStart, r.groupEnd]]] : [])),
    );
    expect(flags).toEqual({
      a: [true, true],
      b: [true, false], // b and c are 3 minutes apart
      c: [false, true],
      d: [true, true], // 17 minutes after c
      e: [true, true], // other side
    });
  });

  it("keys a sent reply by client_id, so the optimistic bubble and the stored one are the same row", () => {
    const [, local] = buildRows([message({ id: "local-k1", client_id: "k1" })], tz);
    const [, stored] = buildRows([message({ id: "m7", client_id: "k1" })], tz);
    expect(local.key).toBe(stored.key);
  });
});

describe("MessageLog (UX-A11Y-03)", () => {
  it("is a polite log and renders every message", () => {
    render(
      <MessageLog
        messages={[message({ id: "a", text: "First" }), message({ id: "b", text: "Second" })]}
        timeZone={tz}
        now={now}
        label="Messages with Priya"
        loading={false}
        hasOlder={false}
        loadingOlder={false}
        loadOlder={() => {}}
        renderMessage={(m) => <p>{m.text}</p>}
      />,
    );
    const log = screen.getByRole("log", { name: "Messages with Priya" });
    expect(log).toHaveAttribute("aria-live", "polite");
    expect(log).toHaveTextContent("First");
    expect(log).toHaveTextContent("Second");
  });

  it("loads older pages near the top and keeps the reader's place (UX-INB-06)", () => {
    const b = message({ id: "b", text: "B", occurred_at: "2026-09-28T09:00:00Z" });
    const c = message({ id: "c", text: "C", occurred_at: "2026-09-28T09:10:00Z" });
    const a = message({ id: "a", text: "A", occurred_at: "2026-09-28T08:00:00Z" });
    const loadOlder = vi.fn();
    const props = { timeZone: tz, now, label: "Messages", loading: false, hasOlder: true, loadingOlder: false, loadOlder, renderMessage: (m: { text?: string | null }) => <p>{m.text}</p> };
    const { rerender } = render(<MessageLog messages={[b, c]} {...props} />);
    const log = screen.getByRole("log");
    // jsdom has no layout: give the log a size and a scroll position.
    let height = 1000;
    let top = 0;
    Object.defineProperty(log, "scrollHeight", { configurable: true, get: () => height });
    Object.defineProperty(log, "clientHeight", { configurable: true, get: () => 500 });
    Object.defineProperty(log, "scrollTop", { configurable: true, get: () => top, set: (v: number) => (top = v) });

    top = 150;
    fireEvent.scroll(log);
    expect(loadOlder).toHaveBeenCalled();

    height = 1600; // the older page adds 600 px above
    rerender(<MessageLog messages={[a, b, c]} {...props} />);
    expect(top).toBe(750);

    // At the bottom, a new message scrolls into view.
    top = height - 500;
    fireEvent.scroll(log);
    height = 1700;
    rerender(<MessageLog messages={[a, b, c, message({ id: "d", text: "D", occurred_at: "2026-09-28T09:20:00Z" })]} {...props} />);
    expect(top).toBe(1700);
  });

  it("shows bubble skeletons while loading", () => {
    render(
      <MessageLog
        messages={[]}
        timeZone={tz}
        now={now}
        label="Messages"
        loading
        hasOlder={false}
        loadingOlder={false}
        loadOlder={() => {}}
        renderMessage={() => null}
      />,
    );
    expect(screen.getByLabelText("Loading messages")).toBeInTheDocument();
  });
});
