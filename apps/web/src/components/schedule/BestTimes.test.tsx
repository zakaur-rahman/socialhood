import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, renderWithApi } from "@/test/api";
import { bestTimes } from "@/test/composer-fixtures";

import { BestTimeHint, BestTimesPanel } from "./BestTimes";

const PATH = "GET /v1/w/:wid/social-accounts/:id/best-times";

describe("BestTimeHint (GR-30)", () => {
  it("suggests the best time for the picked day and fills it in", async () => {
    const onUse = vi.fn();
    renderWithApi(<BestTimeHint wid="w1" accountId="a1" handle="@maple.bakery" date="2026-10-26" today="2026-10-24" onUse={onUse} />, {
      handlers: { [PATH]: () => json(bestTimes()) },
    });
    expect(await screen.findByText(/Best time for @maple.bakery on Mondays/)).toHaveTextContent("18:00");
    fireEvent.click(screen.getByRole("button", { name: "Use 18:00" }));
    expect(onUse).toHaveBeenCalledWith({ date: "2026-10-26", time: "18:00" });
  });

  it("says when the picked weekday has no suggestion", async () => {
    renderWithApi(<BestTimeHint wid="w1" accountId="a1" handle="@maple.bakery" date="2026-10-27" today="2026-10-24" onUse={vi.fn()} />, {
      handlers: { [PATH]: () => json(bestTimes()) },
    });
    expect(await screen.findByText(/No best time for @maple.bakery on Tuesdays yet/)).toBeInTheDocument();
  });

  it("before a day is picked, offers the best days with the date they would take", async () => {
    const onUse = vi.fn();
    renderWithApi(<BestTimeHint wid="w1" accountId="a1" handle="@maple.bakery" date="" today="2026-10-24" onUse={onUse} />, {
      handlers: { [PATH]: () => json(bestTimes()) },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Use Wednesday 12:00" }));
    expect(onUse).toHaveBeenCalledWith({ date: "2026-10-28", time: "12:00" });
  });

  it("says there is not enough history, and shows nothing when the answer fails", async () => {
    const { unmount } = renderWithApi(
      <BestTimeHint wid="w1" accountId="a1" handle="@maple.bakery" date="" today="2026-10-24" onUse={vi.fn()} />,
      { handlers: { [PATH]: () => json(bestTimes({ enough_history: false, sample_size: 3 })) } },
    );
    expect(await screen.findByText("Not enough history for best times yet: 3 of 10 posts with engagement.")).toBeInTheDocument();
    unmount();
    renderWithApi(<BestTimeHint wid="w1" accountId="a1" handle="@maple.bakery" date="" today="2026-10-24" onUse={vi.fn()} />, {});
    await waitFor(() => expect(screen.queryByLabelText("Loading best times")).not.toBeInTheDocument());
    expect(screen.queryByTestId("best-times-hint")).not.toBeInTheDocument();
  });
});

describe("BestTimesPanel (GR-30)", () => {
  it("lists a time per weekday with its basis, and adds one to the week", async () => {
    const onAdd = vi.fn();
    const week: string[][] = Array.from({ length: 7 }, () => []);
    week[2] = ["12:00"];
    renderWithApi(<BestTimesPanel wid="w1" accountId="a1" existing={week} onAdd={onAdd} />, {
      handlers: { [PATH]: () => json(bestTimes()) },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Add 18:00 on Monday" }));
    expect(onAdd).toHaveBeenCalledWith(0, "18:00");
    expect(screen.getByRole("button", { name: "Add 12:00 on Wednesday" })).toBeDisabled(); // already a posting time
    expect(screen.getByText("12 posts, 34% above a typical post")).toBeInTheDocument();
    expect(screen.getAllByText("Not enough posts at one hour")).toHaveLength(5);
    expect(screen.getByText("The hour whose posts did best on each weekday.")).toBeInTheDocument();
  });

  it("explains too little history", async () => {
    renderWithApi(<BestTimesPanel wid="w1" accountId="a1" existing={[]} onAdd={vi.fn()} />, {
      handlers: { [PATH]: () => json(bestTimes({ enough_history: false, sample_size: 0 })) },
    });
    expect(await screen.findByText(/Not enough history for best times yet: 0 of 10/)).toBeInTheDocument();
  });
});
