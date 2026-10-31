import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScrollBox } from "./ScrollBox";

describe("ScrollBox (C-159)", () => {
  it("is a named region keyboard users can reach, so a wide table can be scrolled without a mouse", () => {
    render(
      <ScrollBox label="How long we keep each kind of data">
        <table>
          <tbody>
            <tr>
              <td>Messages</td>
            </tr>
          </tbody>
        </table>
      </ScrollBox>,
    );
    const region = screen.getByRole("region", { name: "How long we keep each kind of data" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveClass("overflow-x-auto");
    expect(region.querySelector("table")).not.toBeNull();
  });
});
