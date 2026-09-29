/**
 * The answer's markdown subset (schemas/agent.py): paragraphs, **bold**, bullet ("- ") and
 * numbered ("1. ") lists, and pipe tables with a header row. `[n]` cites item n of answer_refs
 * (1-based). Everything else (headings, links, images, code, HTML) stays plain text: this parser
 * only produces text, bold, citations and structure, and the renderer builds React elements from
 * them, so nothing in an answer is ever interpreted as HTML.
 */

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; children: Inline[] }
  /** n is 1-based and within the answer's refs. */
  | { type: "cite"; n: number };

export type Align = "left" | "right" | "center" | null;

export type Block =
  /** Lines kept as written: single line breaks inside a paragraph stay line breaks. */
  | { type: "paragraph"; lines: Inline[][] }
  | { type: "list"; ordered: boolean; start: number; items: Inline[][] }
  | {
      type: "table";
      header: Inline[][];
      /** Per column: the separator's alignment, else right for columns of figures. */
      align: Align[];
      rows: Inline[][][];
    };

const BULLET = /^\s{0,3}[-*•]\s+(.*)$/;
const NUMBERED = /^\s{0,3}(\d{1,3})[.)]\s+(.*)$/;
const SEPARATOR_CELL = /^:?-+:?$/;
const CITATION = /\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]/g;
/** A table cell that is a figure: 4,120 · +42% · −8.8% · 6.1 · 1.2k · — */
const FIGURE = /^[+\-−]?[₹$€£]?\d[\d,]*(\.\d+)?\s?(%|k|K|m|M|x|×)?$|^[—–-]$/;

// ---- inline: **bold** and [n]

function citations(text: string, refCount: number): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    const numbers = match[1].split(",").map((part) => Number(part.trim()));
    if (!numbers.every((n) => Number.isInteger(n) && n >= 1 && n <= refCount)) continue;
    const index = match.index ?? 0;
    if (index > last) out.push({ type: "text", text: text.slice(last, index) });
    for (const n of numbers) out.push({ type: "cite", n });
    last = index + match[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}

/** Text, bold runs (not nested) and citations; an unclosed ** stays as written. */
export function parseInline(text: string, refCount: number): Inline[] {
  const out: Inline[] = [];
  let rest = text;
  while (rest.length > 0) {
    const open = rest.indexOf("**");
    const close = open === -1 ? -1 : rest.indexOf("**", open + 2);
    if (open === -1 || close === -1 || close === open + 2) {
      out.push(...citations(rest, refCount));
      break;
    }
    if (open > 0) out.push(...citations(rest.slice(0, open), refCount));
    out.push({ type: "bold", children: citations(rest.slice(open + 2, close), refCount) });
    rest = rest.slice(close + 2);
  }
  return merge(out);
}

/** Adjacent text pieces become one. */
function merge(inlines: Inline[]): Inline[] {
  const out: Inline[] = [];
  for (const inline of inlines) {
    const previous = out[out.length - 1];
    if (inline.type === "text" && previous?.type === "text") {
      out[out.length - 1] = { type: "text", text: previous.text + inline.text };
    } else if (inline.type !== "text" || inline.text !== "") out.push(inline);
  }
  return out;
}

/** The text of inlines without markup, e.g. to decide whether a cell is a figure. */
export function plainText(inlines: Inline[]): string {
  return inlines
    .map((inline) =>
      inline.type === "text" ? inline.text : inline.type === "bold" ? plainText(inline.children) : "",
    )
    .join("");
}

// ---- tables

/** The cells of a pipe row; "\|" is a literal bar. */
export function splitRow(line: string): string[] {
  let body = line.trim();
  if (body.startsWith("|")) body = body.slice(1);
  if (body.endsWith("|") && !body.endsWith("\\|")) body = body.slice(0, -1);
  const cells: string[] = [];
  let current = "";
  for (let i = 0; i < body.length; i++) {
    const char = body[i];
    if (char === "\\" && body[i + 1] === "|") {
      current += "|";
      i++;
    } else if (char === "|") {
      cells.push(current.trim());
      current = "";
    } else current += char;
  }
  cells.push(current.trim());
  return cells;
}

function isSeparator(line: string): boolean {
  if (!line.includes("-")) return false;
  const cells = splitRow(line);
  return cells.length > 0 && cells.every((cell) => SEPARATOR_CELL.test(cell));
}

function alignOf(cell: string): Align {
  const left = cell.startsWith(":");
  const right = cell.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return null;
}

function isTableStart(lines: string[], i: number): boolean {
  return lines[i].includes("|") && i + 1 < lines.length && isSeparator(lines[i + 1]);
}

function fit(cells: string[], width: number): string[] {
  const out = cells.slice(0, width);
  while (out.length < width) out.push("");
  return out;
}

// ---- blocks

type ListDraft = { ordered: boolean; start: number; items: string[] };

export function parseAnswer(source: string, refCount: number): Block[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  // The block being collected: a paragraph's lines or a list's items.
  const open: { paragraph: string[] | null; list: ListDraft | null } = { paragraph: null, list: null };

  const flush = () => {
    const { paragraph, list } = open;
    if (paragraph) blocks.push({ type: "paragraph", lines: paragraph.map((line) => parseInline(line, refCount)) });
    if (list) {
      blocks.push({
        type: "list",
        ordered: list.ordered,
        start: list.start,
        items: list.items.map((item) => parseInline(item, refCount)),
      });
    }
    open.paragraph = null;
    open.list = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim() === "") {
      flush();
      continue;
    }
    if (isTableStart(lines, i)) {
      flush();
      const header = splitRow(line);
      const width = header.length;
      const separator = fit(splitRow(lines[i + 1]), width);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
        rows.push(fit(splitRow(lines[i]), width));
        i++;
      }
      i--; // the loop's i++ moves past the table
      const parsedRows = rows.map((row) => row.map((cell) => parseInline(cell, refCount)));
      const align = separator.map((cell, column) => {
        const explicit = alignOf(cell);
        if (explicit) return explicit;
        const values = parsedRows.map((row) => plainText(row[column]).trim()).filter(Boolean);
        return values.length > 0 && values.every((value) => FIGURE.test(value)) ? "right" : null;
      });
      blocks.push({ type: "table", header: header.map((cell) => parseInline(cell, refCount)), align, rows: parsedRows });
      continue;
    }
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    if (bullet || numbered) {
      const ordered = numbered !== null;
      const text = numbered ? numbered[2] : (bullet?.[1] ?? "");
      if (open.list && open.list.ordered === ordered) open.list.items.push(text);
      else {
        flush();
        open.list = { ordered, start: numbered ? Number(numbered[1]) : 1, items: [text] };
      }
      continue;
    }
    if (open.list && /^\s{2,}\S/.test(line)) {
      // An indented line continues the item above it.
      open.list.items[open.list.items.length - 1] += ` ${line.trim()}`;
      continue;
    }
    if (open.list) flush();
    if (open.paragraph) open.paragraph.push(line.trim());
    else open.paragraph = [line.trim()];
  }
  flush();
  return blocks;
}

/**
 * The answer as plain text for Copy: no ** markers or [n] citations, lists as "- " or "1. "
 * lines, tables as tab-separated rows (they paste into a sheet). Every [n] goes, in range or not.
 */
export function answerToPlainText(answer: string): string {
  const tidy = (text: string) =>
    text
      .replace(/[ \t]+([.,;:!?)])/g, "$1")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  // Cite everything, so every [n] (up to 999) is recognised and dropped.
  const blocks = parseAnswer(answer, 999);
  const lines = blocks.map((block) => {
    if (block.type === "paragraph") return block.lines.map((line) => tidy(plainText(line))).join("\n");
    if (block.type === "list") {
      return block.items
        .map((item, index) => `${block.ordered ? `${block.start + index}.` : "-"} ${tidy(plainText(item))}`)
        .join("\n");
    }
    return [block.header, ...block.rows].map((row) => row.map((cell) => tidy(plainText(cell))).join("\t")).join("\n");
  });
  return lines.join("\n\n");
}

/** The citation numbers an answer uses, in order of first use. */
export function citedNumbers(blocks: Block[]): number[] {
  const seen = new Set<number>();
  const visit = (inlines: Inline[]) => {
    for (const inline of inlines) {
      if (inline.type === "cite") seen.add(inline.n);
      else if (inline.type === "bold") visit(inline.children);
    }
  };
  for (const block of blocks) {
    if (block.type === "paragraph") block.lines.forEach(visit);
    else if (block.type === "list") block.items.forEach(visit);
    else {
      block.header.forEach(visit);
      block.rows.forEach((row) => row.forEach(visit));
    }
  }
  return [...seen];
}
