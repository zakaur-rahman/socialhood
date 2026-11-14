/** The YouTube mark: a rounded rectangle with a play triangle (lucide's Youtube icon is deprecated brand art). Decorative: pair it with text. */
export function YouTubeGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden>
      <path d="M3.5 8.2c.2-1.4 1.3-2.4 2.7-2.6C8 5.3 10 5.2 12 5.2s4 .1 5.8.4c1.4.2 2.5 1.2 2.7 2.6.2 1.2.3 2.6.3 3.8s-.1 2.6-.3 3.8c-.2 1.4-1.3 2.4-2.7 2.6-1.8.3-3.8.4-5.8.4s-4-.1-5.8-.4c-1.4-.2-2.5-1.2-2.7-2.6-.2-1.2-.3-2.6-.3-3.8s.1-2.6.3-3.8z" strokeLinejoin="round" />
      <path d="m10 9.6 4.5 2.4-4.5 2.4z" fill="currentColor" strokeLinejoin="round" />
    </svg>
  );
}
