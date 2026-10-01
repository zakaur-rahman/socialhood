import { useState } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ToggleGroup, ToggleGroupItem } from "./toggle-group"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)

function Single({
  onValueChange = () => {},
  ...props
}: {
  onValueChange?: (value: string) => void
  variant?: "segmented" | "chips"
  size?: "default" | "sm"
  disabled?: string
}) {
  const [value, setValue] = useState("7d")
  return (
    <ToggleGroup
      aria-label="Period"
      variant={props.variant}
      size={props.size}
      value={value}
      onValueChange={(next) => {
        onValueChange(next)
        setValue(next)
      }}
    >
      <ToggleGroupItem value="7d">7 days</ToggleGroupItem>
      <ToggleGroupItem value="30d">30 days</ToggleGroupItem>
      <ToggleGroupItem value="custom" disabled={props.disabled === "custom"}>
        Custom
      </ToggleGroupItem>
    </ToggleGroup>
  )
}

function Multiple({ onValueChange }: { onValueChange: (value: string[]) => void }) {
  const [value, setValue] = useState<string[]>(["ig"])
  return (
    <ToggleGroup
      type="multiple"
      variant="chips"
      aria-label="Accounts"
      value={value}
      onValueChange={(next) => {
        onValueChange(next)
        setValue(next)
      }}
    >
      <ToggleGroupItem value="ig">@shop</ToggleGroupItem>
      <ToggleGroupItem value="wa">WhatsApp</ToggleGroupItem>
    </ToggleGroup>
  )
}

describe("ToggleGroup (segmented)", () => {
  it("is a radio group whose chosen segment is checked, and never empties", async () => {
    const onValueChange = vi.fn()
    render(<Single onValueChange={onValueChange} />)
    expect(screen.getByRole("radiogroup", { name: "Period" })).toBeInTheDocument()
    const week = screen.getByRole("radio", { name: "7 days" })
    const month = screen.getByRole("radio", { name: "30 days" })
    expect(week).toHaveAttribute("aria-checked", "true")

    await userEvent.click(month)
    expect(onValueChange).toHaveBeenLastCalledWith("30d")
    expect(month).toHaveAttribute("aria-checked", "true")
    expect(week).toHaveAttribute("aria-checked", "false")

    // Clicking the chosen segment keeps it.
    onValueChange.mockClear()
    await userEvent.click(month)
    expect(onValueChange).not.toHaveBeenCalled()
    expect(month).toHaveAttribute("aria-checked", "true")
  })

  it("moves between segments with the arrow keys and chooses with Space", async () => {
    render(<Single />)
    await userEvent.tab()
    expect(screen.getByRole("radio", { name: "7 days" })).toHaveFocus()
    await userEvent.keyboard("{ArrowRight}")
    const month = screen.getByRole("radio", { name: "30 days" })
    expect(month).toHaveFocus()
    await userEvent.keyboard(" ")
    expect(month).toHaveAttribute("aria-checked", "true")
  })

  it("draws the chosen segment raised with brand text and no shadow, on a field track", () => {
    render(<Single />)
    const track = screen.getByRole("radiogroup")
    expect(track).toHaveClass("inline-flex", "w-full", "gap-1", "rounded-lg", "bg-field", "p-1")
    expect(track).toHaveAttribute("data-variant", "segmented")
    const item = screen.getByRole("radio", { name: "7 days" })
    expect(item).toHaveClass("rounded-md", "data-[state=on]:bg-raised", "data-[state=on]:text-brand-fg", "text-fg-secondary", "hover:text-fg")
    expect(item).toHaveAttribute("data-state", "on")
    expect(classes(item).filter((c) => c.includes("shadow"))).toEqual([])
  })

  it("keeps the global focus outline, inset, with no halo", () => {
    render(<Single />)
    for (const item of screen.getAllByRole("radio")) {
      const list = classes(item)
      expect(list).toContain("focus-visible:-outline-offset-2")
      expect(list.filter((c) => c.includes("outline-none") || c.includes("outline-hidden") || c.includes("ring"))).toEqual([])
      expect(list).not.toContain("transition-all")
      expect(list).toContain("transition-[color,background-color]")
      expect(list).toContain("duration-fast")
    }
  })

  it("keeps labels on one line, 32 px on fine pointers and 40 px on coarse ones", () => {
    render(<Single />)
    const item = screen.getByRole("radio", { name: "30 days" })
    expect(item).toHaveClass("whitespace-nowrap", "min-h-8", "text-sm", "pointer-coarse:min-h-10")
    expect(item.closest("[data-size]")).toHaveAttribute("data-size", "default")
  })

  it("has a small size: 28 px with 12 px text, still 40 px on coarse pointers", () => {
    render(<Single size="sm" />)
    const item = screen.getByRole("radio", { name: "30 days" })
    expect(item).toHaveClass("min-h-7", "text-xs", "pointer-coarse:min-h-10", "whitespace-nowrap")
    expect(item).not.toHaveClass("min-h-8")
    expect(item).not.toHaveClass("text-sm")
    expect(screen.getByRole("radiogroup")).toHaveAttribute("data-size", "sm")
  })

  it("lets call-site leftovers win until the sweeps remove them", () => {
    render(
      <ToggleGroup aria-label="View" value="week" onValueChange={() => {}}>
        <ToggleGroupItem value="week" className="min-h-10 md:min-h-7 text-xs">
          Week
        </ToggleGroupItem>
      </ToggleGroup>
    )
    const item = screen.getByRole("radio", { name: "Week" })
    expect(item).toHaveClass("min-h-10", "md:min-h-7", "text-xs", "pointer-coarse:min-h-10")
    expect(item).not.toHaveClass("min-h-8")
    expect(item).not.toHaveClass("text-sm")
  })

  it("dims a disabled segment and lets pointer events through to a wrapper, like Button", async () => {
    const onValueChange = vi.fn()
    render(<Single onValueChange={onValueChange} disabled="custom" />)
    const custom = screen.getByRole("radio", { name: "Custom" })
    expect(custom).toBeDisabled()
    expect(custom).toHaveClass("disabled:opacity-50", "disabled:pointer-events-none")
    // Arrow keys skip it.
    await userEvent.tab()
    await userEvent.keyboard("{ArrowRight}{ArrowRight}")
    expect(custom).not.toHaveFocus()
    expect(onValueChange).not.toHaveBeenCalled()
  })
})

describe("ToggleGroup (chips)", () => {
  it("draws pills that wrap, selected in brand-soft with brand text and a brand-line edge", () => {
    render(<Single variant="chips" />)
    const row = screen.getByRole("radiogroup", { name: "Period" })
    expect(row).toHaveClass("flex", "flex-wrap", "gap-1.5")
    expect(row).toHaveAttribute("data-variant", "chips")
    expect(classes(row).filter((c) => c.startsWith("bg-") || c.startsWith("p-"))).toEqual([])
    const chip = screen.getByRole("radio", { name: "7 days" })
    expect(chip).toHaveClass(
      "rounded-full",
      "border",
      "border-line",
      "h-7",
      "px-3",
      "text-xs",
      "font-medium",
      "whitespace-nowrap",
      "hover:bg-hover",
      "data-[state=on]:bg-brand-soft",
      "data-[state=on]:text-brand-fg",
      "data-[state=on]:border-brand-line",
      "pointer-coarse:min-h-10",
      "focus-visible:-outline-offset-2"
    )
    expect(classes(chip).filter((c) => c.includes("bg-raised") || c.includes("ring") || c.includes("outline-none"))).toEqual([])
  })

  it("chooses one chip in a single group", async () => {
    const onValueChange = vi.fn()
    render(<Single variant="chips" onValueChange={onValueChange} />)
    await userEvent.click(screen.getByRole("radio", { name: "Custom" }))
    expect(onValueChange).toHaveBeenLastCalledWith("custom")
    expect(screen.getByRole("radio", { name: "Custom" })).toHaveAttribute("aria-checked", "true")
    expect(screen.getByRole("radio", { name: "7 days" })).toHaveAttribute("aria-checked", "false")
  })

  it("toggles any number of chips in a multiple group, announced as pressed", async () => {
    const onValueChange = vi.fn()
    render(<Multiple onValueChange={onValueChange} />)
    expect(screen.getByRole("toolbar", { name: "Accounts" })).toBeInTheDocument()
    expect(screen.queryByRole("radio")).toBeNull()
    const shop = screen.getByRole("button", { name: "@shop" })
    const whatsapp = screen.getByRole("button", { name: "WhatsApp" })
    expect(shop).toHaveAttribute("aria-pressed", "true")
    expect(whatsapp).toHaveAttribute("aria-pressed", "false")

    await userEvent.click(whatsapp)
    expect(onValueChange).toHaveBeenLastCalledWith(["ig", "wa"])
    expect(whatsapp).toHaveAttribute("aria-pressed", "true")

    await userEvent.click(shop)
    await userEvent.click(whatsapp)
    expect(onValueChange).toHaveBeenLastCalledWith([])
    expect(shop).toHaveAttribute("aria-pressed", "false")
    expect(whatsapp).toHaveAttribute("aria-pressed", "false")
  })

  it("ignores size: a chip is always the small-control chip", () => {
    render(<Single variant="chips" size="sm" />)
    const chip = screen.getByRole("radio", { name: "7 days" })
    expect(chip).toHaveClass("h-7", "text-xs")
    expect(chip).not.toHaveClass("min-h-7")
  })
})
