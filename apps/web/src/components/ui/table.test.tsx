import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Card, CardBleed } from "./card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "./table";

function Payments({ scrollLabel }: { scrollLabel?: string }) {
  return (
    <Table scrollLabel={scrollLabel}>
      <TableCaption>Payments, newest first</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Amount</TableHead>
          <TableHead>Invoice</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>28 Sep</TableCell>
          <TableCell className="text-right">₹999</TableCell>
          <TableCell>Invoice</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>28 Aug</TableCell>
          <TableCell className="text-right">₹999</TableCell>
          <TableCell>—</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}

const slot = (name: string) => [...document.querySelectorAll<HTMLElement>(`[data-slot="${name}"]`)];

describe("Table (UI-026)", () => {
  it("is a table named by its caption, with column headers scoped to their columns", () => {
    render(<Payments />);
    const table = screen.getByRole("table", { name: "Payments, newest first" });
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual(["Date", "Amount", "Invoice"]);
    for (const header of headers) expect(header).toHaveAttribute("scope", "col");
    expect(within(table).getAllByRole("row")).toHaveLength(3);
  });

  it("lets a header be a row header", () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableHead scope="row">Reach</TableHead>
            <TableCell>4,120</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByRole("rowheader", { name: "Reach" })).toHaveAttribute("scope", "row");
  });

  it("headers are 12 px medium fg-secondary in sentence case, py-2, on one line", () => {
    render(<Payments />);
    for (const header of slot("table-head")) {
      expect(header).toHaveClass("text-xs", "font-medium", "text-fg-secondary", "py-2", "px-3", "whitespace-nowrap");
      expect([...header.classList].some((c) => c === "uppercase" || c.startsWith("tracking-") || c.startsWith("text-["))).toBe(false);
    }
  });

  it("body is 14 px with tabular figures; cells py-3 px-3, top-aligned; a call site's alignment wins", () => {
    render(<Payments />);
    expect(slot("table")[0]).toHaveClass("text-sm", "tabular-nums", "w-full", "border-collapse");
    for (const cell of slot("table-cell")) expect(cell).toHaveClass("px-3", "py-3", "align-top");
    expect(screen.getAllByRole("cell", { name: "₹999" })[0]).toHaveClass("text-right");
    expect(screen.getByRole("columnheader", { name: "Amount" })).toHaveClass("text-right");
    expect(screen.getByRole("columnheader", { name: "Amount" })).not.toHaveClass("text-left");
  });

  it("divides rows with line-subtle and leaves the last row open", () => {
    render(<Payments />);
    for (const row of slot("table-row")) expect(row).toHaveClass("border-b", "border-line-subtle");
    expect(slot("table-body")[0]).toHaveClass("[&_tr:last-child]:border-0");
  });

  it("pads the edge cells with --card-padding (12 px outside a card)", () => {
    render(<Payments />);
    const container = slot("table-container")[0];
    expect(container).toHaveClass("[--table-edge:var(--card-padding,--spacing(3))]");
    for (const cell of [...slot("table-head"), ...slot("table-cell")]) {
      expect(cell).toHaveClass("first:ps-(--table-edge)", "last:pe-(--table-edge)");
    }
  });

  it("in a Card, bleeds through CardBleed: the card's padding reaches the table's edge cells", () => {
    render(
      <Card padding="roomy">
        <CardBleed>
          <Payments />
        </CardBleed>
      </Card>,
    );
    const bleed = slot("card-bleed")[0];
    expect(bleed).toContainElement(slot("table-container")[0]);
    // The variable is set by the card and inherited by the container's --table-edge.
    expect(slot("card")[0]).toHaveClass("[--card-padding:--spacing(5)]", "md:[--card-padding:--spacing(6)]");
  });

  it("scrolls inside its container, never the page", () => {
    render(<Payments />);
    const container = slot("table-container")[0];
    expect(container).toHaveClass("overflow-x-auto", "max-w-full", "w-full");
    expect(container).not.toHaveAttribute("tabindex");
    expect(screen.queryByRole("region")).toBeNull();
  });

  describe("scrollLabel: a named region that takes keyboard focus while it scrolls", () => {
    const original = window.ResizeObserver;
    afterEach(() => {
      window.ResizeObserver = original;
      vi.restoreAllMocks();
    });

    function measure(scrollWidth: number, clientWidth: number) {
      // An observer that reports as it starts observing, as browsers do.
      window.ResizeObserver = class {
        callback: ResizeObserverCallback;
        constructor(callback: ResizeObserverCallback) {
          this.callback = callback;
        }
        observe() {
          this.callback([], this as unknown as ResizeObserver);
        }
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
      vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(scrollWidth);
      vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(clientWidth);
    }

    it("focusable when the table is wider than its container", () => {
      measure(520, 286);
      render(<Payments scrollLabel="Payments" />);
      const region = screen.getByRole("region", { name: "Payments" });
      expect(region).toHaveAttribute("tabindex", "0");
      expect(region).toHaveClass("overflow-x-auto", "focus-visible:-outline-offset-2");
      expect(region).toContainElement(screen.getByRole("table"));
    });

    it("no extra tab stop when it fits", () => {
      measure(600, 600);
      render(<Payments scrollLabel="Payments" />);
      expect(screen.getByRole("region", { name: "Payments" })).not.toHaveAttribute("tabindex");
    });
  });

  it("the caption is a quiet note under the table, or hidden with sr-only", () => {
    const { rerender } = render(<Payments />);
    expect(slot("table-caption")[0]).toHaveClass("text-xs", "text-fg-secondary", "px-(--table-edge)");
    rerender(
      <Table>
        <TableCaption className="sr-only">Knowledge sources</TableCaption>
        <TableBody>
          <TableRow>
            <TableCell>FAQ</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByRole("table", { name: "Knowledge sources" })).toBeInTheDocument();
    expect(slot("table-caption")[0]).toHaveClass("sr-only");
  });
});
