import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AlertTriangle } from "lucide-react"
import { describe, expect, it, vi } from "vitest"

import { TONE_CLASS, TONES, type Tone } from "@/lib/ui/tone"
import { colorTokens } from "@/styles/tokens"

import { Alert, AlertAction, AlertDescription, AlertTitle, alertVariants } from "./alert"

const classes = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean)
/** The alert around a piece of its text (the text sits in its content block). */
const alertOf = (text: string) => screen.getByText(text).closest("[data-slot=alert]")!

// --- WCAG contrast from the token values (hex, or `rgb(r g b / a)` composited on a surface) ---
type RGB = [number, number, number]
function parse(value: string): { rgb: RGB; alpha: number } {
  if (value.startsWith("#")) {
    const n = parseInt(value.slice(1), 16)
    return { rgb: [(n >> 16) & 255, (n >> 8) & 255, n & 255], alpha: 1 }
  }
  const m = value.match(/^rgb\((\d+) (\d+) (\d+) \/ ([\d.]+)\)$/)
  if (!m) throw new Error(`unparsed colour ${value}`)
  return { rgb: [Number(m[1]), Number(m[2]), Number(m[3])], alpha: Number(m[4]) }
}
const token = (name: string) => {
  const t = colorTokens.find((c) => c.name === name)
  if (!t) throw new Error(`no token ${name}`)
  return parse(t.value)
}
const over = (top: { rgb: RGB; alpha: number }, under: RGB): RGB =>
  top.rgb.map((c, i) => c * top.alpha + under[i] * (1 - top.alpha)) as RGB
const luminance = (rgb: RGB) => {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a: RGB, b: RGB) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
/** "bg-warning-soft text-warning" → ["warning-soft", "warning"]. */
const pair = (tone: Tone) => {
  const list = TONE_CLASS[tone].split(" ")
  return [list.find((c) => c.startsWith("bg-"))!.slice(3), list.find((c) => c.startsWith("text-"))!.slice(5)]
}

describe("Alert", () => {
  it("defaults to a neutral soft alert: UX-SH-04's rounded-lg px-4 py-2.5 text-sm, polite", () => {
    render(<Alert>Replies are paused while you are away.</Alert>)
    const alert = screen.getByRole("status")
    expect(alert).toHaveAttribute("data-slot", "alert")
    expect(alert).toHaveAttribute("data-tone", "neutral")
    expect(alert).toHaveAttribute("data-variant", "soft")
    expect(alert).toHaveClass("rounded-lg", "px-4", "py-2.5", "text-sm", "bg-hover", "text-fg-secondary")
    expect(alert).toHaveTextContent("Replies are paused while you are away.")
    expect(classes(alert).filter((c) => c === "border" || c.startsWith("border-"))).toEqual([])
  })

  it.each(TONES)("soft %s: the tone's soft fill and text from the one tone map, no border", (tone) => {
    render(<Alert tone={tone}>{tone}</Alert>)
    const alert = alertOf(tone)
    expect(alert).toHaveAttribute("data-tone", tone)
    expect(alert).toHaveClass(...TONE_CLASS[tone].split(" "))
    expect(classes(alert).filter((c) => c === "border" || c.startsWith("border-"))).toEqual([])
  })

  it("draws danger text in danger-fg, never danger", () => {
    render(<Alert tone="danger">Payment failed</Alert>)
    const alert = screen.getByRole("alert")
    expect(alert).toHaveClass("bg-danger-soft", "text-danger-fg")
    expect(alert).not.toHaveClass("text-danger")
  })

  it.each([
    ["neutral", "border-l-line-strong", "text-fg-secondary"],
    ["brand", "border-l-brand", "text-brand-fg"],
    ["success", "border-l-success", "text-success"],
    ["warning", "border-l-warning", "text-warning"],
    ["danger", "border-l-danger", "text-danger-fg"],
  ] as const)("outline %s: panel, a line edge and a 2 px %s leading edge; the icon in %s", (tone, edge, iconText) => {
    render(
      <Alert tone={tone} variant="outline" icon={<AlertTriangle data-testid="icon" />}>
        <AlertTitle>Title</AlertTitle>
        <AlertDescription>Description</AlertDescription>
      </Alert>
    )
    const alert = alertOf("Title")
    expect(alert).toHaveAttribute("data-variant", "outline")
    expect(alert).toHaveClass("bg-panel", "border", "border-line", "border-l-2", edge, "text-fg")
    expect(alert).not.toHaveClass(...TONE_CLASS[tone].split(" "))
    expect(screen.getByTestId("icon").parentElement).toHaveClass(iconText)
    // The title is fg and the description fg-secondary on panel (by the alert's data-variant).
    expect(screen.getByText("Title")).toHaveClass("font-semibold", "group-data-[variant=outline]/alert:text-fg")
    expect(screen.getByText("Description")).toHaveClass("group-data-[variant=outline]/alert:text-fg-secondary")
  })

  it("has a semibold title (the Item title role) and a description, fg titles on neutral alerts", () => {
    render(
      <Alert icon={<AlertTriangle data-testid="icon" />}>
        <AlertTitle>Away</AlertTitle>
        <AlertDescription>Replies resume at 9:00.</AlertDescription>
      </Alert>
    )
    expect(screen.getByText("Away")).toHaveAttribute("data-slot", "alert-title")
    expect(screen.getByText("Away")).toHaveClass("font-semibold", "group-data-[tone=neutral]/alert:text-fg")
    expect(screen.getByText("Replies resume at 9:00.")).toHaveAttribute("data-slot", "alert-description")
    const icon = screen.getByTestId("icon").parentElement!
    expect(icon).toHaveAttribute("data-slot", "alert-icon")
    expect(icon).toHaveAttribute("aria-hidden", "true")
    expect(icon).toHaveClass("[&>svg]:size-4", "h-5")
  })

  describe("role by urgency", () => {
    it("is polite (status) for neutral, brand, success and warning", () => {
      for (const tone of ["neutral", "brand", "success", "warning"] as const) {
        const { unmount } = render(<Alert tone={tone}>{tone}</Alert>)
        expect(alertOf(tone)).toHaveAttribute("role", "status")
        expect(alertOf(tone)).not.toHaveAttribute("data-urgent")
        unmount()
      }
    })

    it("is an alert for danger, and for any tone marked urgent", () => {
      render(
        <>
          <Alert tone="danger">Payment failed</Alert>
          <Alert tone="warning" urgent>
            Reconnect Instagram
          </Alert>
          <Alert tone="danger" urgent={false}>
            Still danger
          </Alert>
        </>
      )
      expect(screen.getAllByRole("alert").map((a) => a.textContent)).toEqual([
        "Payment failed",
        "Reconnect Instagram",
        "Still danger",
      ])
      expect(alertOf("Reconnect Instagram")).toHaveAttribute("data-urgent", "true")
    })
  })

  describe("action", () => {
    it("is one secondary sm Button, 40 px on coarse pointers", async () => {
      const onClick = vi.fn()
      render(
        <Alert tone="warning" action={<AlertAction onClick={onClick}>View billing</AlertAction>}>
          Your trial ends in 2 days.
        </Alert>
      )
      const button = screen.getByRole("button", { name: "View billing" })
      expect(button).toHaveAttribute("data-variant", "secondary")
      expect(button).toHaveAttribute("data-size", "sm")
      expect(button).toHaveClass("bg-raised", "text-fg", "h-7", "pointer-coarse:min-h-10")
      expect(button.closest("[data-slot=alert-action]")).not.toBeNull()
      await userEvent.click(button)
      expect(onClick).toHaveBeenCalledOnce()
    })

    it("can be a link, through asChild", () => {
      render(
        <Alert
          tone="danger"
          action={
            <AlertAction asChild>
              <a href="/billing">Manage billing</a>
            </AlertAction>
          }
        >
          Payment failed
        </Alert>
      )
      const link = screen.getByRole("link", { name: "Manage billing" })
      expect(link).toHaveAttribute("href", "/billing")
      expect(link).toHaveClass("bg-raised", "h-7")
    })

    it("sits beside the message from 448 px of alert width and under it below that", () => {
      render(
        <Alert icon={<AlertTriangle data-testid="icon" />} action={<AlertAction>Fix</AlertAction>}>
          Message
        </Alert>
      )
      const content = screen.getByText("Message")
      expect(content).toHaveAttribute("data-slot", "alert-content")
      expect(content.parentElement).toHaveClass("flex-col", "@md/alert:flex-row")
      expect(alertOf("Message")).toHaveClass("@container/alert")
      // Beside the action, the first line is the action's height, so the icon and text centre on it.
      expect(content).toHaveClass("@md/alert:py-1", "@md/alert:pointer-coarse:py-2.5")
      expect(screen.getByTestId("icon").parentElement).toHaveClass("h-5", "@md/alert:h-7", "@md/alert:pointer-coarse:h-10")
    })
  })

  describe("dismiss", () => {
    it("shows a Dismiss icon button on non-critical alerts and calls onDismiss", async () => {
      const onDismiss = vi.fn()
      render(
        <Alert tone="warning" icon={<AlertTriangle data-testid="icon" />} onDismiss={onDismiss}>
          Your trial ends in 2 days.
        </Alert>
      )
      const dismiss = screen.getByRole("button", { name: "Dismiss" })
      expect(dismiss).toHaveAttribute("data-variant", "ghost")
      expect(dismiss).toHaveAttribute("data-size", "icon-sm")
      expect(dismiss).toHaveClass("size-7", "pointer-coarse:size-10")
      await userEvent.click(dismiss)
      expect(onDismiss).toHaveBeenCalledOnce()
      // The first line is as tall as Dismiss, so the icon, the text and the × share a centre line.
      expect(screen.getByText("Your trial ends in 2 days.")).toHaveClass("py-1", "pointer-coarse:py-2.5")
      expect(screen.getByTestId("icon").parentElement).toHaveClass("h-7", "pointer-coarse:h-10")
    })

    it("takes a specific label", () => {
      render(
        <Alert onDismiss={() => {}} dismissLabel="Dismiss the trial reminder">
          Trial
        </Alert>
      )
      expect(screen.getByRole("button", { name: "Dismiss the trial reminder" })).toBeInTheDocument()
    })

    it("is never offered on critical states: danger and urgent alerts", () => {
      render(
        <>
          <Alert tone="danger" onDismiss={() => {}}>
            Payment failed
          </Alert>
          <Alert tone="warning" urgent onDismiss={() => {}}>
            Reconnect Instagram
          </Alert>
        </>
      )
      expect(screen.queryByRole("button", { name: "Dismiss" })).toBeNull()
    })

    it("adds no padding to the text when nothing shares its line", () => {
      render(<Alert>Plain</Alert>)
      const content = screen.getByText("Plain")
      expect(classes(content).filter((c) => c.includes("py-"))).toEqual([])
    })
  })

  it("passes other props through and merges a call-site class", () => {
    render(
      <Alert data-testid="gap" aria-label="Knowledge gaps" className="mt-4">
        Gaps
      </Alert>
    )
    const alert = screen.getByTestId("gap")
    expect(alert).toHaveAttribute("aria-label", "Knowledge gaps")
    expect(alert).toHaveClass("mt-4", "rounded-lg")
  })

  it("uses tokens only: no hex, palette, arbitrary colour, transition or dark: classes", () => {
    for (const variant of ["soft", "outline"] as const) {
      for (const tone of TONES) {
        const list = alertVariants({ variant, tone }).split(/\s+/)
        expect(list.filter((c) => /#|white|black|\/\d|\[|^dark:|^transition|^shadow|^ring/.test(c))).toEqual([])
      }
    }
  })

  describe("contrast (WCAG 4.5:1 for text)", () => {
    it.each(TONES)("%s text on its soft fill, over panel and over canvas", (tone) => {
      const [fill, text] = pair(tone)
      for (const surface of ["panel", "canvas"]) {
        const ratio = contrast(token(text).rgb, over(token(fill), token(surface).rgb))
        expect(ratio, `${text} on ${fill} over ${surface}`).toBeGreaterThanOrEqual(4.5)
      }
    })

    it("fg titles on the neutral fill, and outline text on panel", () => {
      for (const surface of ["panel", "canvas"]) {
        expect(contrast(token("fg").rgb, over(token("hover"), token(surface).rgb))).toBeGreaterThanOrEqual(4.5)
      }
      expect(contrast(token("fg").rgb, token("panel").rgb)).toBeGreaterThanOrEqual(4.5)
      expect(contrast(token("fg-secondary").rgb, token("panel").rgb)).toBeGreaterThanOrEqual(4.5)
    })

    it("outline icons in the tone's text colour reach 4.5:1 on panel (3:1 is the bar for icons)", () => {
      for (const tone of TONES) {
        const [, text] = pair(tone)
        expect(contrast(token(text).rgb, token("panel").rgb)).toBeGreaterThanOrEqual(4.5)
      }
    })
  })
})
