import { ChevronDown } from "lucide-react";

/**
 * A page's table of contents (C-159), shared by the guides and the legal pages: server-rendered links
 * to the page's own section ids, in a `[data-toc]` nav named by `label`. `TocSpy` (an idle-loaded
 * client island) marks the section being read with `aria-current="location"`; with no script the
 * links still work.
 *
 * - `numbered`: each entry shows its number (the legal pages' numbered sections).
 * - `collapsible`: the list sits in a disclosure under the label, closed on a narrower screen and
 *   open beside the text from site-wide (TocSpy opens it; CSS too where it can).
 *
 * Styles: site.css, `.toc` (C-159 shared); a page's block only places it.
 */
export type TocItem = { id: string; label: string };

export function TocNav({
  items,
  label = "On this page",
  className,
  numbered = false,
  collapsible = false,
}: {
  items: readonly TocItem[];
  label?: string;
  className?: string;
  numbered?: boolean;
  collapsible?: boolean;
}) {
  const classes = ["toc", numbered ? "toc-num" : "", className ?? ""].filter(Boolean).join(" ");
  const list = (
    <ol>
      {items.map((item, index) => (
        <li key={item.id}>
          <a href={`#${item.id}`}>
            {numbered ? (
              <>
                <span className="toc-n">{index + 1}</span>
                <span>{item.label}</span>
              </>
            ) : (
              item.label
            )}
          </a>
        </li>
      ))}
    </ol>
  );
  return (
    <nav aria-label={label} className={classes} data-toc="">
      {collapsible ? (
        <details className="toc-d">
          <summary>
            <span className="toc-t">{label}</span>
            <ChevronDown size={18} strokeWidth={1.75} aria-hidden focusable="false" className="toc-chev" />
          </summary>
          {list}
        </details>
      ) : (
        <>
          <p className="toc-t">{label}</p>
          {list}
        </>
      )}
    </nav>
  );
}
