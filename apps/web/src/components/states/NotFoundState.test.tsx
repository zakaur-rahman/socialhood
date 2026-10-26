import { render, screen } from "@testing-library/react";
import type { Route } from "next";
import { describe, expect, it } from "vitest";

import { ApiError, isNotFound } from "@/lib/api/errors";

import { NotFoundState } from "./NotFoundState";

const problem = (status: number, code: string) => new ApiError({ type: "t", title: "t", status, code });

describe("isNotFound", () => {
  it("is true only for an API 404", () => {
    expect(isNotFound(problem(404, "not_found"))).toBe(true);
    expect(isNotFound(problem(500, "internal"))).toBe(false);
    expect(isNotFound(problem(403, "forbidden"))).toBe(false);
    expect(isNotFound(new Error("x"))).toBe(false);
  });
});

describe("NotFoundState", () => {
  it("names the thing and links back to its list", () => {
    render(<NotFoundState thing="post" backHref={"/w/maple/schedule" as Route} backLabel="Back to Schedule" />);
    expect(screen.getByText("This post doesn't exist or was deleted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Schedule" })).toHaveAttribute("href", "/w/maple/schedule");
  });
});
