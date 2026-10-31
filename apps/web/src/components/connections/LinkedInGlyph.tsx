/** The LinkedIn mark, drawn in the same stroke style as the other platform glyphs. Decorative: pair it with text. */
export function LinkedInGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M8 10.5V16M8 7.75v.01M12 16v-5.5M12 13a2.5 2.5 0 0 1 5 0v3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
