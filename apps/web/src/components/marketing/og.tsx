import { ImageResponse } from "next/og";

import { OG_IMAGE, SITE_NAME } from "@/lib/marketing/site";

// Satori can't read CSS variables, so the token values are written out (globals.css @theme).
const TOKENS = {
  canvas: "#000000",
  panel: "#1F1F1F",
  fg: "#FFFFFF",
  fgSecondary: "#9B9CA0",
  brandFg: "#9DB5FF",
  brandDeep: "#20338A",
  shell1: "#3352CC",
  shell2: "#1C2D70",
  instagram: "#BE185D",
  whatsapp: "#16A34A",
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
          backgroundImage: "radial-gradient(circle at 85% 0%, rgba(86,127,248,0.35), rgba(0,0,0,0) 55%)",
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
            <div
              style={{
                width: 44,
                height: 32,
                borderRadius: 8,
                background: TOKENS.fg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 5,
              }}
            >
              {[0, 1, 2].map((dot) => (
                <div key={dot} style={{ width: 7, height: 7, borderRadius: 7, background: TOKENS.brandDeep }} />
              ))}
            </div>
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
