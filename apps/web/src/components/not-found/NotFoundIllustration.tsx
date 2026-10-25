/**
 * The 404 illustration: a short chat thread whose last message has wandered off. Inline SVG from
 * the theme tokens only (fill-*, stroke-*, so it follows light and dark), decorative (aria-hidden;
 * the page's heading says what happened). The lost bubble bobs and the dots twinkle through the
 * `nf-*` utilities in globals.css, which switch the motion off under reduced motion.
 */
export function NotFoundIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 220" fill="none" aria-hidden focusable="false" className={className} data-testid="not-found-illustration">
      {/* the glow behind the scene */}
      <ellipse cx="160" cy="196" rx="112" ry="12" className="fill-line-subtle" />
      <circle cx="160" cy="104" r="84" className="fill-brand-soft" />

      {/* the thread: one message in, one out */}
      <g>
        <rect x="46" y="62" width="112" height="36" rx="14" className="fill-raised stroke-line-control" strokeWidth="1.5" />
        <path d="M58 98 L52 110 L72 98 Z" className="fill-raised stroke-line-control" strokeWidth="1.5" strokeLinejoin="round" />
        <rect x="62" y="75" width="64" height="5" rx="2.5" className="fill-fg-secondary" opacity="0.55" />
        <rect x="62" y="85" width="40" height="5" rx="2.5" className="fill-fg-secondary" opacity="0.35" />
      </g>
      <g>
        <rect x="150" y="116" width="124" height="36" rx="14" className="fill-brand stroke-brand-deep" strokeWidth="1.5" />
        <path d="M262 152 L270 164 L248 152 Z" className="fill-brand stroke-brand-deep" strokeWidth="1.5" strokeLinejoin="round" />
        <rect x="166" y="129" width="72" height="5" rx="2.5" className="fill-on-brand" opacity="0.9" />
        <rect x="166" y="139" width="44" height="5" rx="2.5" className="fill-on-brand" opacity="0.6" />
      </g>

      {/* the trail the lost message left, and the message itself */}
      <path
        d="M196 56 C 214 44, 226 30, 250 28"
        className="stroke-line-control"
        strokeWidth="1.5"
        strokeDasharray="2 6"
        strokeLinecap="round"
      />
      <g className="nf-drift">
        <rect x="236" y="8" width="64" height="40" rx="14" className="fill-panel stroke-brand" strokeWidth="1.5" strokeDasharray="5 4" />
        <path d="M246 48 L242 58 L258 48 Z" className="fill-panel stroke-brand" strokeWidth="1.5" strokeLinejoin="round" />
        <text x="268" y="36" textAnchor="middle" className="fill-brand-fg" fontSize="24" fontWeight="600">
          ?
        </text>
      </g>

      {/* stars of the quiet kind */}
      <circle cx="40" cy="38" r="2.5" className="fill-brand-fg nf-twinkle" />
      <circle cx="84" cy="22" r="1.8" className="fill-fg-secondary nf-twinkle nf-twinkle-late" />
      <circle cx="292" cy="96" r="2" className="fill-brand-fg nf-twinkle nf-twinkle-late" />
      <circle cx="26" cy="132" r="1.8" className="fill-fg-secondary nf-twinkle" />

      {/* the number, small, under the thread */}
      <text x="160" y="190" textAnchor="middle" className="fill-fg-secondary" fontSize="13" fontWeight="500" letterSpacing="6">
        4 0 4
      </text>
    </svg>
  );
}
