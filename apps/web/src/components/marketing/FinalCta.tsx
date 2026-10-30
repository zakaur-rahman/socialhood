import { ArrowRight, Check } from "lucide-react";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import type { Platform } from "@/lib/api/types";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { Ico } from "./landing/Ico";
import { CtaLink, LogoMark } from "./primitives";

/**
 * The convergence drawn above the closer's heading (C-159 final CTA), on a 560 × 160 field: each
 * channel's mark on the outside, a stream from it into the Amplychat mark at the centre. The streams
 * leave each mark level and arrive level at the hub, so the two on each side join before they land.
 * `x` and `y` place the mark's centre in the field's units; the curve is drawn from the mark to the hub.
 */
const STREAMS: { platform: Platform; colour: string; x: number; y: number; d: string }[] = [
  { platform: "instagram", colour: "var(--ig)", x: 40, y: 36, d: "M40 36C170 36 150 80 280 80" },
  { platform: "whatsapp", colour: "var(--wa)", x: 40, y: 124, d: "M40 124C170 124 150 80 280 80" },
  { platform: "web", colour: "var(--web)", x: 520, y: 36, d: "M520 36C390 36 410 80 280 80" },
  { platform: "facebook", colour: "var(--fb)", x: 520, y: 124, d: "M520 124C390 124 410 80 280 80" },
];

/** Every customer conversation into one inbox, drawn: decorative, so hidden from assistive tech. */
function Converge() {
  return (
    <div className="converge" aria-hidden>
      <svg className="cv-lines" viewBox="0 0 560 160" fill="none" aria-hidden focusable="false">
        {STREAMS.map((stream, index) => (
          <path key={stream.platform} d={stream.d} pathLength={1} className="cv-line" style={{ "--n": index } as CSSProperties} />
        ))}
      </svg>
      {STREAMS.map((stream, index) => (
        <Ico
          key={stream.platform}
          className="ico-mark cv-mark"
          style={{ "--c": stream.colour, "--x": stream.x, "--y": stream.y, "--n": index } as CSSProperties}
        >
          <PlatformGlyph platform={stream.platform} />
        </Ico>
      ))}
      <span className="cv-hub">
        <LogoMark className="size-full rounded-none" />
      </span>
    </div>
  );
}

/**
 * The last call to action, on a night band (C-155; C-157: one action, the email as a line of text;
 * C-159 final CTA: a centred finale under the channels converging into one mark, drawn once as it
 * scrolls in, with no loop). `trialDays` is Pro's trial when Pro is on sale, so the perk is only
 * claimed when it can be taken (C-149).
 */
export function FinalCta({ trialDays = 0 }: { trialDays?: number }) {
  const perks = [
    "Free plan, no card needed",
    ...(trialDays > 0 ? [`${trialDays}-day trial of Pro`] : []),
    "Official Meta APIs, no password asked",
  ];
  return (
    <section className="night close" aria-labelledby="cta-title">
      <div className="wrap close-in">
        <Converge />
        <h2 id="cta-title" className="close-h">
          Bring every customer conversation into one inbox
        </h2>
        <p className="close-p">
          Connect Instagram, WhatsApp and your website chat, add what your business knows, and let the AI draft the replies.
        </p>
        <div className="ctas">
          <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
            Start free <ArrowRight className="size-4" aria-hidden />
          </CtaLink>
        </div>
        <ul className="facts" aria-label="What you get">
          {perks.map((perk) => (
            <li key={perk}>
              <Check className="size-4" strokeWidth={2.4} aria-hidden />
              {perk}
            </li>
          ))}
        </ul>
        <p className="close-mail">
          Questions? Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
        </p>
      </div>
    </section>
  );
}
