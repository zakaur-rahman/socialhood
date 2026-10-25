import { screen, within } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";

/**
 * Drives ui/date-picker's DatePicker the way a person does: opens the button named `label`, pages
 * the calendar to the month of `day` ("YYYY-MM-DD") and clicks the day. The picker's value is that
 * same string, so a test that used to type it into a native date input passes the same text here.
 */
export async function pickDate(user: UserEvent, label: string | HTMLElement, day: string, scope: Pick<typeof screen, "getByLabelText"> = screen) {
  const trigger = typeof label === "string" ? scope.getByLabelText(label) : label;
  await user.click(trigger);
  const grid = await screen.findByRole("grid");
  for (let hops = 0; hops < 48; hops++) {
    const cell = grid.querySelector(`td[data-day="${day}"]:not([data-outside])`);
    if (cell) {
      await user.click(within(cell as HTMLElement).getByRole("button"));
      return;
    }
    const shown = grid.querySelector("td[data-day]:not([data-outside])")?.getAttribute("data-day") ?? day;
    await user.click(screen.getByRole("button", { name: day < shown ? /previous month/i : /next month/i }));
  }
  throw new Error(`The calendar never showed ${day}`);
}
