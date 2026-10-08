import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { TONE_CLASS, TONES } from "@/lib/ui/tone"

import { Badge, badgeVariants } from "./badge"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)

describe("Badge", () => {
  it("defaults to a neutral 11 px pill, 20 px tall", () => {
    render(<Badge>Draft</Badge>)
    const badge = screen.getByText("Draft")
    expect(badge).toHaveAttribute("data-slot", "badge")
    expect(badge).toHaveAttribute("data-tone", "neutral")
    expect(badge).toHaveAttribute("data-size", "sm")
    expect(badge).toHaveAttribute("data-shape", "pill")
    expect(badge).toHaveClass("h-5", "px-2", "text-2xs", "font-medium", "whitespace-nowrap", "rounded-full", "bg-hover", "text-fg-secondary")
  })

  it.each(TONES)("reads the %s tone from the one tone map", (tone) => {
    render(<Badge tone={tone}>{tone}</Badge>)
    const badge = screen.getByText(tone)
    expect(badge).toHaveAttribute("data-tone", tone)
    expect(badge).toHaveClass(...TONE_CLASS[tone].split(" "))
  })

  it("draws the status tones on their soft fills, with danger text in danger-fg", () => {
    render(
      <>
        <Badge tone="brand">Scheduled</Badge>
        <Badge tone="success">Published</Badge>
        <Badge tone="warning">Partly published</Badge>
        <Badge tone="danger">Failed</Badge>
      </>
    )
    expect(screen.getByText("Scheduled")).toHaveClass("bg-brand-soft", "text-brand-fg")
    expect(screen.getByText("Published")).toHaveClass("bg-success-soft", "text-success")
    expect(screen.getByText("Partly published")).toHaveClass("bg-warning-soft", "text-warning")
    expect(screen.getByText("Failed")).toHaveClass("bg-danger-soft", "text-danger-fg")
    expect(screen.getByText("Failed")).not.toHaveClass("text-danger")
  })

  it("draws a count on the brand gradient with on-brand tabular figures, a circle for one digit", () => {
    render(
      <Badge tone="count" size="md">
        3
      </Badge>
    )
    const badge = screen.getByText("3")
    expect(badge).toHaveClass("bg-brand-gradient", "text-on-brand", "tabular-nums", "h-5", "min-w-5", "px-1.5", "text-xs", "rounded-full")
    expect(badge).not.toHaveClass("px-2")
    expect(classes(badge).filter((c) => c === "text-white" || c.startsWith("bg-hover"))).toEqual([])
  })

  it("has two sizes: sm 11 px and md 12 px, both 20 px tall", () => {
    render(
      <>
        <Badge size="sm">Small</Badge>
        <Badge size="md">Medium</Badge>
      </>
    )
    expect(screen.getByText("Small")).toHaveClass("text-2xs", "h-5")
    expect(screen.getByText("Small")).not.toHaveClass("text-xs")
    expect(screen.getByText("Medium")).toHaveClass("text-xs", "h-5", "px-2")
    expect(screen.getByText("Medium")).not.toHaveClass("text-2xs")
  })

  it("has a tag shape with 4 px corners for thumbnail labels", () => {
    render(<Badge shape="tag">Reel</Badge>)
    const badge = screen.getByText("Reel")
    expect(badge).toHaveAttribute("data-shape", "tag")
    expect(badge).toHaveClass("rounded-sm")
    expect(badge).not.toHaveClass("rounded-full")
  })

  it("isn't a control: no transition, no ring, no arbitrary radius or size", () => {
    for (const tone of [...TONES, "count"] as const) {
      const list = badgeVariants({ tone }).split(/\s+/)
      expect(list.filter((c) => c.startsWith("transition") || c.includes("ring") || c.includes("rounded-4xl") || c.includes("text-["))).toEqual([])
      expect(list.filter((c) => c.startsWith("dark:"))).toEqual([])
    }
  })

  it("renders as its child with asChild, and a call-site class still merges", () => {
    render(
      <Badge asChild tone="brand" className="gap-1.5">
        <a href="/plans">Pro</a>
      </Badge>
    )
    const link = screen.getByRole("link", { name: "Pro" })
    expect(link).toHaveAttribute("data-slot", "badge")
    expect(link).toHaveClass("bg-brand-soft", "gap-1.5")
    expect(link).not.toHaveClass("gap-1")
  })
})
