import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Skeleton } from "./skeleton"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)

describe("Skeleton", () => {
  it("is raised, so it shows on panel, and pulses only without reduced motion", () => {
    render(<Skeleton data-testid="s" className="h-3 w-20" />)
    const s = screen.getByTestId("s")
    expect(s).toHaveAttribute("data-slot", "skeleton")
    expect(s).toHaveClass("bg-raised", "motion-safe:animate-pulse", "rounded-md", "h-3", "w-20")
    const list = classes(s)
    expect(list).not.toContain("animate-pulse")
    expect(list).not.toContain("bg-muted")
  })

  it("keeps a call site's surface until the sweeps remove the overrides", () => {
    render(<Skeleton data-testid="s" className="bg-panel motion-reduce:animate-none" />)
    const s = screen.getByTestId("s")
    expect(s).toHaveClass("bg-panel", "motion-reduce:animate-none", "motion-safe:animate-pulse")
    expect(s).not.toHaveClass("bg-raised")
  })
})
