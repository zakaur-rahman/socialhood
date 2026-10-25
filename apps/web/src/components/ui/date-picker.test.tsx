import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it } from "vitest";

import { DatePicker, DateTimePicker, parseTime, timeSlots } from "@/components/ui/date-picker";
import { Field, FieldLabel } from "@/components/ui/field";
import { dayLabel, formatDay, parseDay } from "@/lib/day";
import { pickDate } from "@/test/datepicker";

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {};
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
});

function Picker({ initial = "2026-09-28", min, max }: { initial?: string; min?: string; max?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <p>Saved: {value || "none"}</p>
      <Field id="when">
        <FieldLabel>Send on</FieldLabel>
        <DatePicker value={value} onChange={setValue} min={min} max={max} today="2026-09-28" clearable />
      </Field>
    </>
  );
}

describe("day strings", () => {
  it("round-trips YYYY-MM-DD without a time zone and rejects impossible days", () => {
    expect(formatDay(parseDay("2026-02-28")!)).toBe("2026-02-28");
    expect(parseDay("2026-02-30")).toBeUndefined();
    expect(parseDay("")).toBeUndefined();
    expect(dayLabel("2026-09-28")).toBe("Mon 28 Sep 2026");
  });

  it("reads times as typed: strict HH:mm, or loosely on leaving the field", () => {
    expect(parseTime("9:30")).toBe("09:30");
    expect(parseTime("930")).toBeNull();
    expect(parseTime("930", true)).toBe("09:30");
    expect(parseTime("18", true)).toBe("18:00");
    expect(parseTime("24:00")).toBeNull();
    expect(parseTime("10:60")).toBeNull();
    expect(timeSlots()).toHaveLength(96);
  });
});

describe("DatePicker", () => {
  it("is the Field's labelled control and shows the chosen day", () => {
    render(<Picker />);
    const trigger = screen.getByLabelText("Send on");
    expect(trigger).toHaveRole("button");
    expect(trigger).toHaveTextContent("Mon 28 Sep 2026");
    expect(trigger).toHaveClass("bg-field", "border-line-control", "rounded-lg");
  });

  it("opens a calendar on the chosen month, and choosing a day sets the same YYYY-MM-DD string and closes it", async () => {
    const user = userEvent.setup();
    render(<Picker />);
    await pickDate(user, "Send on", "2026-10-02");
    expect(screen.getByText("Saved: 2026-10-02")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("grid")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Send on")).toHaveTextContent("Fri 2 Oct 2026");
  });

  it("disables days outside min and max", async () => {
    const user = userEvent.setup();
    render(<Picker min="2026-09-26" max="2026-09-30" />);
    await user.click(screen.getByLabelText("Send on"));
    const grid = await screen.findByRole("grid");
    expect(grid.querySelector('td[data-day="2026-09-25"] button')).toBeDisabled();
    expect(grid.querySelector('td[data-day="2026-09-26"] button')).toBeEnabled();
    expect(grid.querySelector('td[data-day="2026-09-30"] button')).toBeEnabled();
    expect(grid.querySelector('td[data-day="2026-10-01"]')).toHaveAttribute("data-outside");
  });

  it("keyboard: focus lands on the chosen day, arrows move, Enter chooses, Esc closes with focus back on the button", async () => {
    const user = userEvent.setup();
    render(<Picker />);
    const trigger = screen.getByLabelText("Send on");
    trigger.focus();
    await user.keyboard("{Enter}");
    await screen.findByRole("grid");
    await waitFor(() => expect(document.activeElement).toHaveAttribute("data-day", "2026-09-28"));
    await user.keyboard("{ArrowRight}");
    expect(document.activeElement).toHaveAttribute("data-day", "2026-09-29");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Saved: 2026-09-29")).toBeInTheDocument();

    await user.keyboard("{Enter}");
    await screen.findByRole("grid");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("grid")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    expect(screen.getByText("Saved: 2026-09-29")).toBeInTheDocument();
  });

  it("clears when clearable", async () => {
    const user = userEvent.setup();
    render(<Picker />);
    await user.click(screen.getByRole("button", { name: "Clear date" }));
    expect(screen.getByText("Saved: none")).toBeInTheDocument();
    expect(screen.getByLabelText("Send on")).toHaveTextContent("Pick a date");
  });
});

describe("DateTimePicker", () => {
  function Both() {
    const [value, setValue] = useState({ date: "2026-09-28", time: "18:30" });
    return (
      <>
        <p>Saved: {value.date} {value.time}</p>
        <DateTimePicker idPrefix="when" value={value} onChange={setValue} today="2026-09-28" />
      </>
    );
  }

  it("holds {date, time} strings: typed times, picked quarter-hours and loose input all give HH:mm", async () => {
    const user = userEvent.setup();
    render(<Both />);
    const time = screen.getByLabelText("Time");
    expect(time).toHaveValue("18:30");

    await user.clear(time);
    await user.type(time, "9:07");
    expect(screen.getByText("Saved: 2026-09-28 09:07")).toBeInTheDocument();

    await user.clear(time);
    await user.type(time, "1415");
    await user.tab();
    expect(screen.getByText("Saved: 2026-09-28 14:15")).toBeInTheDocument();
    expect(time).toHaveValue("14:15");

    await user.click(screen.getByRole("button", { name: "Choose a time" }));
    await user.click(await screen.findByRole("option", { name: "21:00" }));
    expect(screen.getByText("Saved: 2026-09-28 21:00")).toBeInTheDocument();
    expect(time).toHaveValue("21:00");

    await pickDate(user, "Date", "2026-10-01");
    expect(screen.getByText("Saved: 2026-10-01 21:00")).toBeInTheDocument();
  });
});

describe("DatePicker with jumpMonths", () => {
  function Jump({ min, max }: { min?: string; max?: string }) {
    const [value, setValue] = useState("2026-09-28");
    return (
      <>
        <p>Saved: {value}</p>
        <Field id="far">
          <FieldLabel>Start</FieldLabel>
          <DatePicker value={value} onChange={setValue} min={min} max={max} today="2026-09-28" jumpMonths />
        </Field>
      </>
    );
  }

  it("jumps to another month and year from the caption", async () => {
    const user = userEvent.setup();
    render(<Jump min="2026-01-15" max="2028-06-30" />);
    await user.click(screen.getByLabelText("Start"));
    await user.click(await screen.findByRole("combobox", { name: /year/i }));
    const years = within(await screen.findByRole("listbox")).getAllByRole("option").map((o) => o.textContent);
    expect(years).toEqual(["2026", "2027", "2028"]);
    await user.click(screen.getByRole("option", { name: "2028" }));
    await user.click(screen.getByRole("combobox", { name: /month/i }));
    await user.click(await screen.findByRole("option", { name: "March" }));
    await user.click(within(await screen.findByRole("grid")).getByRole("button", { name: /15/ }));
    expect(screen.getByText("Saved: 2028-03-15")).toBeInTheDocument();
  });
});
