import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Avatar, AvatarBadge, AvatarFallback } from "./avatar"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)

function Contact({ size }: { size?: "sm" | "default" | "lg" }) {
  return (
    <Avatar size={size} data-testid="avatar">
      <AvatarFallback>P</AvatarFallback>
      <AvatarBadge className="bg-instagram" data-testid="badge">
        <svg data-testid="glyph" />
      </AvatarBadge>
    </Avatar>
  )
}

describe("AvatarBadge", () => {
  it("cuts the platform badge out of the picture with a 2 px panel ring", () => {
    render(<Contact />)
    const badge = screen.getByTestId("badge")
    expect(badge).toHaveAttribute("data-slot", "avatar-badge")
    expect(badge).toHaveClass("absolute", "-right-0.5", "-bottom-0.5", "rounded-full", "ring-2", "ring-panel", "text-on-brand")
    const list = classes(badge)
    expect(list).not.toContain("ring-background")
    expect(list.filter((c) => c.startsWith("border"))).toEqual([])
  })

  it("takes the platform fill from the caller", () => {
    render(<Contact />)
    const badge = screen.getByTestId("badge")
    expect(badge).toHaveClass("bg-instagram")
    expect(badge).not.toHaveClass("bg-primary")
  })

  it("sizes the badge and its glyph with the avatar", () => {
    render(<Contact size="lg" />)
    expect(screen.getByTestId("avatar")).toHaveAttribute("data-size", "lg")
    expect(screen.getByTestId("badge")).toHaveClass(
      "group-data-[size=sm]/avatar:size-2",
      "group-data-[size=default]/avatar:size-3.5",
      "group-data-[size=default]/avatar:[&>svg]:size-2",
      "group-data-[size=lg]/avatar:size-4",
      "group-data-[size=lg]/avatar:[&>svg]:size-2.5"
    )
  })
})

describe("Avatar", () => {
  it("has no dark: classes (the app is dark only) and keeps its lightened edge", () => {
    render(<Contact />)
    const list = classes(screen.getByTestId("avatar"))
    expect(list.filter((c) => c.startsWith("dark:"))).toEqual([])
    expect(list).toContain("after:mix-blend-lighten")
    expect(list).not.toContain("after:mix-blend-darken")
  })
})
