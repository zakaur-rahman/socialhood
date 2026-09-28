/** The WhatsApp mark: a speech bubble with a handset (lucide has no brand icons). Decorative. */
export function WhatsAppGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden>
      <path d="M3.5 20.5l1.3-4.2A8.5 8.5 0 1 1 8 19.3z" strokeLinejoin="round" />
      <path
        d="M9 8.6c0 3 2.4 5.9 5.6 6.4.5.1 1-.2 1.3-.6l.4-.7-1.8-1-.8.8c-1.2-.5-2.1-1.4-2.6-2.6l.8-.8-1-1.8-.7.4c-.4.3-.7.7-.6 1.2z"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}
