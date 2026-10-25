import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SequenceAnalytics } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { percent, SequenceNumbers } from "./SequenceNumbers";

function analytics(values: Partial<SequenceAnalytics> = {}): SequenceAnalytics {
  return {
    sequence_id: "s1",
    window_hours: 24,
    computed_at: "2026-10-26T09:00:00Z",
    enrolled: 4,
    active: 2,
    completed: 1,
    stopped: 1,
    stopped_by: [{ code: "reply", text: "They replied", count: 1 }],
    sent: 5,
    skipped: 1,
    skipped_by: [{ code: "no_consent", text: "They haven't agreed to WhatsApp marketing messages.", count: 1 }],
    failed: 0,
    replied: 2,
    reply_rate: 0.4,
    steps: [
      { position: 1, reached: 4, waiting: 0, sent: 3, skipped: 1, failed: 0, replied: 2, reply_rate: 0.6667, share: 1 },
      { position: 2, reached: 2, waiting: 2, sent: 0, skipped: 0, failed: 0, replied: 0, reply_rate: null, share: 0.5 },
    ],
    ...values,
  } as SequenceAnalytics;
}

function setup(numbers: SequenceAnalytics) {
  return renderWithApi(<SequenceNumbers sequenceId="s1" />, {
    handlers: { "GET /v1/w/:wid/sequences/:id/analytics": () => json(numbers) },
  });
}

describe("a sequence's numbers (GR-24)", () => {
  it("formats a rate, and says none yet when nothing was sent", () => {
    expect(percent(0.4)).toBe("40%");
    expect(percent(null)).toBe("none yet");
  });

  it("shows what the server counted: totals, reasons and the funnel", async () => {
    setup(analytics());
    expect(await screen.findByText("Entered")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("They haven't agreed to WhatsApp marketing messages.")).toBeInTheDocument();
    expect(screen.getByText("They replied")).toBeInTheDocument();
    const funnel = screen.getAllByRole("meter");
    expect(funnel).toHaveLength(2);
    expect(within(funnel[1].parentElement as HTMLElement).getByText(/2 of 4 reached it/)).toBeInTheDocument();
    expect(screen.getByText(/3 sent, 1 skipped, 0 failed\. Replies: 67%/)).toBeInTheDocument();
    expect(screen.getByText(/2 waiting/)).toBeInTheDocument();
  });

  it("says so when nobody has entered", async () => {
    setup(analytics({ enrolled: 0, active: 0, completed: 0, stopped: 0, stopped_by: [], steps: [] }));
    expect(await screen.findByText(/Nobody has entered this sequence yet/)).toBeInTheDocument();
  });
});
