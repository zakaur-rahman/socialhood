import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";

import { LOGO_BARS, LOGO_BUBBLE_PATH } from "@/components/marketing/primitives";
import { OG_IMAGE, SITE_NAME } from "@/lib/marketing/site";
import { colorValue } from "@/styles/tokens";

// Satori can't read CSS variables, so the values come from styles/tokens.ts (UI-ISS-095).
const TOKENS = {
  paper: colorValue("paper"),
  ink: colorValue("ink"),
  inkSecondary: colorValue("ink-secondary"),
  iris: colorValue("iris"),
  shell1: colorValue("shell-1"),
  shell2: colorValue("shell-2"),
  brandDeep: colorValue("brand-deep"),
  onBrand: colorValue("on-brand"),
};

/** Geist at weight 700 (SIL OFL), the site's heading face; Satori reads static TTF, not the variable woff2. */
const FONT_PATH = ["src", "components", "marketing", "fonts", "Geist-Bold.ttf"];

/** The tagline under the headline: the channels, named plainly. */
export const OG_CHANNELS_LINE = "For Instagram, WhatsApp and website chat.";

/**
 * The share card for every public page (Open Graph and Twitter), drawn with next/og on the site's
 * paper. The route is force-static, so it is drawn once at build time and cached (C-157).
 */
export async function renderOgImage(): Promise<ImageResponse> {
  const font = await readFile(join(process.cwd(), ...FONT_PATH));
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          backgroundColor: TOKENS.paper,
          color: TOKENS.ink,
          fontFamily: "Geist",
          fontWeight: 700,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 18,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundImage: `linear-gradient(135deg, ${TOKENS.shell1}, ${TOKENS.shell2})`,
            }}
          >
            <svg width="64" height="64" viewBox="0 0 64 64">
              <path d={LOGO_BUBBLE_PATH} fill={TOKENS.onBrand} />
              {LOGO_BARS.map(([x, y, height]) => (
                <rect key={x} x={x} y={y} width="5" height={height} rx="2.5" fill={TOKENS.brandDeep} />
              ))}
            </svg>
          </div>
          <div style={{ fontSize: 36, letterSpacing: -1 }}>{SITE_NAME}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          <div style={{ display: "flex", flexDirection: "column", fontSize: 100, lineHeight: 1.02, letterSpacing: -4 }}>
            <div>Every DM.</div>
            <div>Every comment.</div>
            <div style={{ color: TOKENS.iris }}>One inbox.</div>
          </div>
          <div style={{ fontSize: 34, letterSpacing: -0.5, color: TOKENS.inkSecondary }}>{OG_CHANNELS_LINE}</div>
        </div>
      </div>
    ),
    {
      width: OG_IMAGE.width,
      height: OG_IMAGE.height,
      fonts: [{ name: "Geist", data: font, weight: 700, style: "normal" }],
    },
  );
}
