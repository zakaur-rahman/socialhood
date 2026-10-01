import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)

function Panel({ size }: { size?: "default" | "sm" }) {
  return (
    <Tabs defaultValue="preview">
      <TabsList aria-label="Automation panel" size={size}>
        <TabsTrigger value="preview">Preview</TabsTrigger>
        <TabsTrigger value="test">Test</TabsTrigger>
        <TabsTrigger value="runs" disabled>
          Runs
        </TabsTrigger>
        <TabsTrigger value="stats">Stats</TabsTrigger>
      </TabsList>
      <TabsContent value="preview">Preview panel</TabsContent>
      <TabsContent value="test">Test panel</TabsContent>
      <TabsContent value="runs">Runs panel</TabsContent>
      <TabsContent value="stats">Stats panel</TabsContent>
    </Tabs>
  )
}

describe("Tabs", () => {
  it("is a tab list whose tabs control their panels", () => {
    render(<Panel />)
    const list = screen.getByRole("tablist", { name: "Automation panel" })
    expect(list).toBeInTheDocument()
    const preview = screen.getByRole("tab", { name: "Preview" })
    expect(preview).toHaveAttribute("aria-selected", "true")
    const panel = screen.getByRole("tabpanel", { name: "Preview" })
    expect(preview).toHaveAttribute("aria-controls", panel.id)
    expect(panel).toHaveTextContent("Preview panel")
  })

  it("moves with the arrow keys, skipping a disabled tab, and swaps the panel", async () => {
    render(<Panel />)
    await userEvent.tab()
    expect(screen.getByRole("tab", { name: "Preview" })).toHaveFocus()
    await userEvent.keyboard("{ArrowRight}")
    const test = screen.getByRole("tab", { name: "Test" })
    expect(test).toHaveFocus()
    expect(test).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Test panel")
    await userEvent.keyboard("{ArrowRight}")
    expect(screen.getByRole("tab", { name: "Stats" })).toHaveFocus()
  })

  it("looks like the segmented control: raised brand-text segment on a field track, no shadow", () => {
    render(<Panel />)
    expect(screen.getByRole("tablist")).toHaveClass("grid", "auto-cols-fr", "grid-flow-col", "gap-1", "rounded-lg", "bg-field", "p-1")
    const tab = screen.getByRole("tab", { name: "Preview" })
    expect(tab).toHaveAttribute("data-state", "active")
    expect(tab).toHaveClass(
      "rounded-md",
      "text-fg-secondary",
      "data-[state=active]:bg-raised",
      "data-[state=active]:text-brand-fg",
      "whitespace-nowrap",
      "min-h-8",
      "text-sm",
      "pointer-coarse:min-h-10"
    )
    expect(classes(tab).filter((c) => c.includes("shadow"))).toEqual([])
  })

  it("keeps the global focus outline, inset on tabs, and on a focusable panel", () => {
    render(<Panel />)
    for (const tab of screen.getAllByRole("tab")) {
      const list = classes(tab)
      expect(list).toContain("focus-visible:-outline-offset-2")
      expect(list.filter((c) => c.includes("outline-none") || c.includes("outline-hidden") || c.includes("ring"))).toEqual([])
    }
    const panel = screen.getByRole("tabpanel")
    expect(panel).toHaveAttribute("tabindex", "0")
    expect(classes(panel).filter((c) => c.includes("outline-none") || c.includes("outline-hidden"))).toEqual([])
  })

  it("has the small size, set once on the list", () => {
    render(<Panel size="sm" />)
    expect(screen.getByRole("tablist")).toHaveAttribute("data-size", "sm")
    for (const tab of screen.getAllByRole("tab")) {
      expect(tab).toHaveClass("min-h-7", "text-xs", "pointer-coarse:min-h-10")
      expect(tab).not.toHaveClass("min-h-8")
    }
  })

  it("dims a disabled tab, which takes no pointer events (a DisabledReason wrapper gets them)", () => {
    render(<Panel />)
    const runs = screen.getByRole("tab", { name: "Runs" })
    expect(runs).toBeDisabled()
    expect(runs).toHaveClass("disabled:opacity-50", "disabled:pointer-events-none")
  })
})
