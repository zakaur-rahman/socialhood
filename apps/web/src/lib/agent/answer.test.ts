import { describe, expect, it } from "vitest";

import { citedNumbers, parseAnswer, parseInline, plainText, splitRow, type Block } from "./answer";

describe("answer inline markup (the markdown subset)", () => {
  it("reads **bold** and [n] citations within the answer's references", () => {
    expect(parseInline("Reach was **4,120** [1], up 42% [2].", 2)).toEqual([
      { type: "text", text: "Reach was " },
      { type: "bold", children: [{ type: "text", text: "4,120" }] },
      { type: "text", text: " " },
      { type: "cite", n: 1 },
      { type: "text", text: ", up 42% " },
      { type: "cite", n: 2 },
      { type: "text", text: "." },
    ]);
  });

  it("keeps out-of-range citations, unclosed bold and empty bold as written", () => {
    expect(parseInline("See [3] and [0].", 2)).toEqual([{ type: "text", text: "See [3] and [0]." }]);
    expect(parseInline("a **b", 1)).toEqual([{ type: "text", text: "a **b" }]);
    expect(parseInline("a **** b", 1)).toEqual([{ type: "text", text: "a **** b" }]);
  });

  it("reads grouped citations like [1, 2] and citations inside bold", () => {
    expect(parseInline("both [1, 2]", 2)).toEqual([
      { type: "text", text: "both " },
      { type: "cite", n: 1 },
      { type: "cite", n: 2 },
    ]);
    expect(parseInline("**top post [1]**", 1)).toEqual([
      { type: "bold", children: [{ type: "text", text: "top post " }, { type: "cite", n: 1 }] },
    ]);
  });

  it("leaves HTML, links, headings and code as plain text", () => {
    const html = '<img src=x onerror="alert(1)"> [site](https://evil.example) `code` <script>x</script>';
    expect(parseInline(html, 0)).toEqual([{ type: "text", text: html }]);
    expect(parseAnswer("## Heading", 0)).toEqual([
      { type: "paragraph", lines: [[{ type: "text", text: "## Heading" }]] },
    ]);
  });
});

describe("answer blocks", () => {
  it("splits paragraphs on blank lines and keeps single line breaks", () => {
    const blocks = parseAnswer("First line\nsecond line\n\nNext paragraph", 0);
    expect(blocks).toEqual([
      {
        type: "paragraph",
        lines: [[{ type: "text", text: "First line" }], [{ type: "text", text: "second line" }]],
      },
      { type: "paragraph", lines: [[{ type: "text", text: "Next paragraph" }]] },
    ]);
  });

  it("reads bullet and numbered lists, their start, and indented continuations", () => {
    const blocks = parseAnswer(
      "Top topics:\n- too expensive: 31\n- shipping cost: 14\n  mostly Dubai\n\n3. third\n4. fourth\nDone.",
      0,
    );
    expect(blocks.map((b) => b.type)).toEqual(["paragraph", "list", "list", "paragraph"]);
    const bullets = blocks[1] as Extract<Block, { type: "list" }>;
    expect(bullets.ordered).toBe(false);
    expect(bullets.items.map(plainText)).toEqual(["too expensive: 31", "shipping cost: 14 mostly Dubai"]);
    const numbered = blocks[2] as Extract<Block, { type: "list" }>;
    expect(numbered).toMatchObject({ ordered: true, start: 3 });
    expect(numbered.items.map(plainText)).toEqual(["third", "fourth"]);
  });

  it("reads a pipe table with its header, alignment and figure columns", () => {
    const blocks = parseAnswer(
      "Compared at 24 hours:\n| Metric | This reel | Note |\n|:---|---|:---:|\n| Reach | 4,120 | good |\n| Rate | 6.1% | fine [1] |",
      1,
    );
    expect(blocks[0].type).toBe("paragraph");
    const table = blocks[1] as Extract<Block, { type: "table" }>;
    expect(table.type).toBe("table");
    expect(table.header.map(plainText)).toEqual(["Metric", "This reel", "Note"]);
    // Explicit alignments win; a column of figures is right-aligned.
    expect(table.align).toEqual(["left", "right", "center"]);
    expect(table.rows.map((row) => row.map(plainText))).toEqual([
      ["Reach", "4,120", "good"],
      ["Rate", "6.1%", "fine "],
    ]);
    expect(citedNumbers(blocks)).toEqual([1]);
  });

  it("pads short rows, drops extra cells and keeps escaped bars", () => {
    const table = parseAnswer("| a | b |\n|---|---|\n| 1 |\n| x \\| y | 2 | 3 |", 0)[0] as Extract<Block, { type: "table" }>;
    expect(table.rows.map((row) => row.map(plainText))).toEqual([
      ["1", ""],
      ["x | y", "2"],
    ]);
    expect(splitRow("| a | b |")).toEqual(["a", "b"]);
  });

  it("a line with bars but no separator row is a paragraph", () => {
    expect(parseAnswer("a | b\nc | d", 0)[0].type).toBe("paragraph");
  });
});
