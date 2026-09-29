"""Knowledge test support: small PDF and DOCX files built in memory, and a fake DNS for web-page
sources (tests never reach a real website: patch ``ssrf.resolve_host`` with ``fake_dns``)."""

from __future__ import annotations

import io
from collections.abc import Awaitable, Callable

import docx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

PUBLIC_IP = "93.184.216.34"
PRIVATE_IP = "10.0.0.7"
HOSTS = {
    "maple.example": [PUBLIC_IP],
    "www.maple.example": [PUBLIC_IP],
    "intranet.maple.example": [PRIVATE_IP],
}


def make_pdf(*pages: list[str]) -> bytes:
    """A PDF with one page per list of lines (Helvetica text pypdf can extract)."""
    writer = PdfWriter()
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({escaped}) Tj T*")
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        page.replace_contents(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_docx(blocks: list[tuple[str, str]], table: list[list[str]] | None = None) -> bytes:
    """A Word document: ("h1", text) headings and ("p", text) paragraphs, then a table."""
    document = docx.Document()
    for kind, text in blocks:
        if kind == "h1":
            document.add_heading(text, level=1)
        else:
            document.add_paragraph(text)
    if table:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                grid.cell(r, c).text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def fake_dns(table: dict[str, list[str]]) -> Callable[[str, int], Awaitable[list[str]]]:
    async def resolve(host: str, port: int) -> list[str]:
        if host not in table:
            raise OSError(f"no such host {host}")
        return table[host]

    return resolve
