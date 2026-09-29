"""Text from web pages and files (TR-AI-08, FR-KB-01).

Web pages: the main text by trafilatura, as Markdown so headings survive for chunking. Files:
PDF by pypdf, DOCX by python-docx (headings become ``#`` lines, table rows become ``a | b``
lines), TXT and MD as UTF-8 text. These are synchronous and CPU-bound; callers run them in a
thread. Failures raise ``ExtractError`` with a reason in plain words.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

import docx
import pypdf
import trafilatura
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf.errors import PdfReadError, PyPdfError

from socialhood.services.knowledge.chunking import normalise
from socialhood.services.media_assets import KNOWLEDGE_FILE, KNOWLEDGE_UNSUPPORTED

FILE_FORMATS = KNOWLEDGE_FILE.formats  # FR-KB-01: PDF, DOCX, TXT, MD
MAX_FILE_BYTES = KNOWLEDGE_FILE.max_bytes  # 10 MB
FILE_FORMATS_COPY = KNOWLEDGE_UNSUPPORTED
UNREADABLE_DOCX = "Couldn't read this Word document. Save it as .docx and try again."


class ExtractError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class WebText:
    text: str
    title: str | None


def web_page(html: bytes, url: str | None = None) -> WebText:
    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=False,
        favor_recall=True,
    )
    cleaned = normalise(text or "")
    if not cleaned:
        raise ExtractError("Couldn't find readable text on this page.")
    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = (metadata.title or "").strip() if metadata is not None else ""
    return WebText(text=cleaned, title=title or None)


def file_text(data: bytes, fmt: str) -> str:
    """The text of a PDF, DOCX, TXT or MD file."""
    fmt = fmt.lower()
    if fmt == "pdf":
        text = _pdf(data)
    elif fmt == "docx":
        text = _docx(data)
    elif fmt in ("txt", "md"):
        text = _plain(data)
    else:
        raise ExtractError(FILE_FORMATS_COPY)
    cleaned = normalise(text)
    if not cleaned:
        if fmt == "pdf":
            raise ExtractError(
                "Couldn't find any text in this PDF. Scanned PDFs (pictures of pages) aren't "
                "supported yet."
            )
        raise ExtractError("This file has no text.")
    return cleaned


def _pdf(data: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractError("This PDF is password-protected. Upload a copy without a password.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ExtractError:
        raise
    except (PdfReadError, PyPdfError, ValueError, KeyError, TypeError) as error:
        raise ExtractError("Couldn't read this PDF. It may be damaged.") from error
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _docx(data: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(data))
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                blocks.append(_paragraph(item))
            elif isinstance(item, Table):
                blocks.append(_table(item))
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ExtractError(UNREADABLE_DOCX) from error
    return "\n\n".join(block for block in blocks if block.strip())


def _paragraph(paragraph: Paragraph) -> str:
    text = paragraph.text.strip()
    style = (paragraph.style.name if paragraph.style is not None else "") or ""
    if text and (style.startswith("Heading") or style == "Title"):
        return f"# {text}"
    return text


def _table(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _plain(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")
