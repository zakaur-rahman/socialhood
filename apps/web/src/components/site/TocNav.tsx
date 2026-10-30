/**
 * A page's table of contents (C-159): server-rendered links to the page's own section ids. `TocSpy`
 * (an idle-loaded client island) marks the section being read with `aria-current="location"`; with
 * no script the links still work. Styles: site.css, `.toc` (C-159 guides).
 */
export type TocItem = { id: string; label: string };

export function TocNav({ items, label = "On this page", className }: { items: readonly TocItem[]; label?: string; className?: string }) {
  return (
    <nav aria-label={label} className={className ? `toc ${className}` : "toc"} data-toc="">
      <p className="toc-t">{label}</p>
      <ol>
        {items.map((item) => (
          <li key={item.id}>
            <a href={`#${item.id}`} data-toc-link={item.id}>
              {item.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
