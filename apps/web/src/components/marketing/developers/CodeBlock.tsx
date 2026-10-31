/** A copyable code block in the developer pages (the `.cx-code` style), focusable so a keyboard can scroll it. */
export function Code({ children }: { children: string }) {
  return (
    <pre className="cx-code" tabIndex={0}>
      <code>{children}</code>
    </pre>
  );
}
