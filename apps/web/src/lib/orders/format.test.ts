import { describe, expect, it } from "vitest";

import { actionsFor, amountMinor, customerName, lineName, orderNumber, orderTotal, STATUS_LABEL } from "./format";

describe("order formatting (GR-32)", () => {
  it("shows the number, the total and the lines", () => {
    expect(orderNumber({ number: 12 })).toBe("#12");
    expect(orderTotal({ total_minor: 159800, currency: "INR" })).toMatch(/1,598\.00/);
    expect(lineName({ name: "Cotton kurta", variant_title: "Blue / M", quantity: 2 })).toBe("2 x Cotton kurta - Blue / M");
    expect(lineName({ name: "Scarf", variant_title: null, quantity: 1 })).toBe("1 x Scarf");
  });

  it("names the customer by name, else handle", () => {
    expect(customerName({ contact: { id: "c", display_name: "Priya", username: "priya.s" } })).toBe("Priya");
    expect(customerName({ contact: { id: "c", display_name: null, username: "priya.s" } })).toBe("@priya.s");
    expect(customerName({ contact: { id: "c", display_name: null, username: null } })).toBe("Customer");
  });

  it("allows only what the state allows", () => {
    const none = { pay: false, markPaid: false, cancel: false, edit: false, ship: false, refund: false };
    expect(actionsFor("draft")).toEqual({ ...none, pay: true, markPaid: true, cancel: true, edit: true });
    expect(actionsFor("awaiting_payment")).toEqual({ ...none, pay: true, markPaid: true, cancel: true, edit: true });
    expect(actionsFor("expired")).toEqual({ ...none, pay: true, markPaid: true });
    expect(actionsFor("partially_paid")).toEqual({ ...none, pay: true, markPaid: true, refund: true });
    expect(actionsFor("paid")).toEqual({ ...none, ship: true, refund: true });
    expect(actionsFor("fulfilled")).toEqual({ ...none, refund: true });
    expect(actionsFor("refunded")).toEqual(none);
    expect(actionsFor("cancelled")).toEqual(none);
  });

  it("names every status", () => {
    expect(STATUS_LABEL.partially_paid).toBe("Partly paid");
    expect(STATUS_LABEL.fulfilled).toBe("Shipped");
    expect(STATUS_LABEL.refunded).toBe("Refunded");
  });

  it("reads an amount a member typed as minor units", () => {
    expect(amountMinor("500", "INR")).toBe(50000);
    expect(amountMinor("1,598.50", "INR")).toBe(159850);
    expect(amountMinor("499.5", "INR")).toBe(49950);
    expect(amountMinor("1500", "JPY")).toBe(1500);
    expect(amountMinor("0", "INR")).toBeNull();
    expect(amountMinor("abc", "INR")).toBeNull();
    expect(amountMinor("1.234", "INR")).toBeNull();
    expect(amountMinor("", "INR")).toBeNull();
  });
});
