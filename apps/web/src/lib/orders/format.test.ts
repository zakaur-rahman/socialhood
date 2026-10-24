import { describe, expect, it } from "vitest";

import { actionsFor, customerName, lineName, orderNumber, orderTotal } from "./format";

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
    expect(actionsFor("draft")).toEqual({ pay: true, markPaid: true, cancel: true });
    expect(actionsFor("expired")).toEqual({ pay: true, markPaid: true, cancel: false });
    expect(actionsFor("paid")).toEqual({ pay: false, markPaid: false, cancel: false });
    expect(actionsFor("cancelled")).toEqual({ pay: false, markPaid: false, cancel: false });
  });
});
