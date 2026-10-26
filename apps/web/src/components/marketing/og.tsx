import { ImageResponse } from "next/og";

import { LOGO_BARS, LOGO_BUBBLE_PATH } from "@/components/marketing/primitives";
import { OG_IMAGE, SITE_NAME } from "@/lib/marketing/site";
import { colorValue } from "@/styles/tokens";

/** `rgb(r g b / a)` as `rgba(r,g,b,a)`: Satori parses only the comma form. */
function legacyRgba(value: string): string {
  const match = value.match(/^rgb\((\d+) (\d+) (\d+) \/ ([\d.]+)\)$/);
  if (!match) throw new Error(`Not an rgb() token: ${value}`);
  return `rgba(${match.slice(1).join(",")})`;
}

// Satori can't read CSS variables, so the values come from styles/tokens.ts (UI-ISS-095).
const TOKENS = {
  canvas: colorValue("canvas"),
  panel: colorValue("panel"),
  fg: colorValue("fg"),
  fgSecondary: colorValue("fg-secondary"),
  brandFg: colorValue("brand-fg"),
  brandDeep: colorValue("brand-deep"),
  brandLine: legacyRgba(colorValue("brand-line")),
  shell1: colorValue("shell-1"),
  shell2: colorValue("shell-2"),
  instagram: colorValue("instagram"),
  whatsapp: colorValue("whatsapp"),
};

/** The share card for every public page (Open Graph and Twitter), drawn with next/og. */
export function renderOgImage(): ImageResponse {
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
          backgroundColor: TOKENS.canvas,
          backgroundImage: `radial-gradient(circle at 85% 0%, ${TOKENS.brandLine}, rgba(0,0,0,0) 55%)`,
          color: TOKENS.fg,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundImage: `linear-gradient(135deg, ${TOKENS.shell1}, ${TOKENS.shell2})`,
            }}
          >
            <svg width="72" height="72" viewBox="0 0 64 64">
              <path d={LOGO_BUBBLE_PATH} fill={TOKENS.fg} />
              {LOGO_BARS.map(([x, y, height]) => (
                <rect key={x} x={x} y={y} width="5" height={height} rx="2.5" fill={TOKENS.brandDeep} />
              ))}
            </svg>
          </div>
          <div style={{ fontSize: 40, fontWeight: 600, letterSpacing: -1 }}>{SITE_NAME}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 68, fontWeight: 700, lineHeight: 1.08, letterSpacing: -2, maxWidth: 1000 }}>
            The AI inbox for businesses that sell on Instagram and WhatsApp
          </div>
          <div style={{ fontSize: 30, color: TOKENS.fgSecondary, maxWidth: 980, lineHeight: 1.35 }}>
            Replies from your own business knowledge, comment and DM automations, in English, Hindi and Hinglish.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 24, color: TOKENS.brandFg }}>
          <div style={{ width: 14, height: 14, borderRadius: 14, background: TOKENS.instagram }} />
          Instagram
          <div style={{ width: 14, height: 14, borderRadius: 14, background: TOKENS.whatsapp, marginLeft: 16 }} />
          WhatsApp
        </div>
      </div>
    ),
    { width: OG_IMAGE.width, height: OG_IMAGE.height },
  );
}
