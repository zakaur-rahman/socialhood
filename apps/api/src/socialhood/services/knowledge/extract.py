"""Text from web pages and files (TR-AI-08, FR-KB-01).

Web pages: the main text by trafilatura, as Markdown so headings survive for chunking. Files:
PDF by pypdf, DOCX by python-docx (headings become ``#`` lines, table rows become ``a | b``
lines), TXT and MD as UTF-8 text. These are synchronous and CPU-bound; callers run them in a
thread. Failures raise ``ExtractError`` with a reason in plain words.

An uploaded file is read by ``file_text_isolated``, in a child process with its own memory cap and
a time limit: what a compressed format expands to can't be known before reading it, and the worker
process is shared by every workspace.
"""

from __future__ import annotations

import io
import subprocess
import sys
import threading
import zipfile
import zlib
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
UNREADABLE_FILE = "Couldn't read this file. It may be damaged or too complex. Try a smaller copy."
TOO_MUCH_TEXT = "This file has more text than we can read. Split it into smaller files."

MB = 1024 * 1024
# Real Word files stay far below these: they hold XML, which python-docx parses (about ten times
# its size in memory), and pictures, which barely compress.
MAX_DOCX_PARTS = 5000
MAX_DOCX_PART_BYTES = 32 * MB
MAX_DOCX_TOTAL_BYTES = 64 * MB
MAX_DOCX_RATIO = 300  # deflate tops out near 1000:1; XML rarely passes 100:1
DOCX_RATIO_FROM_BYTES = MB  # small parts may compress as well as they like
_READ_CHUNK = 64 * 1024

MAX_TEXT_CHARS = 20_000_000
ISOLATED_TIMEOUT_S = 90.0
ISOLATED_MEMORY_BYTES = 400 * MB  # on top of what the child uses once its imports are done
_ISOLATED_SLOTS = threading.BoundedSemaphore(2)  # across workspaces, so two children at worst


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


def file_text_isolated(data: bytes, fmt: str) -> str:
    """``file_text`` in a child process. Past its memory cap or time limit the child dies and the
    file fails with a plain reason; nothing else in the worker is affected."""
    command = [sys.executable, "-m", __name__, fmt]
    with _ISOLATED_SLOTS:
        try:
            child = subprocess.run(  # noqa: S603 (our interpreter and module; fmt is an argument)
                command,
                input=data,
                capture_output=True,
                timeout=ISOLATED_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ExtractError(UNREADABLE_FILE) from error
    if child.returncode == _REFUSED_EXIT:
        raise ExtractError(child.stdout.decode())
    if child.returncode != 0:
        raise ExtractError(UNREADABLE_FILE)
    return child.stdout.decode()


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


def _check_docx_size(data: bytes) -> None:
    """Refuse a Word file that would inflate too far, before python-docx reads it. Counts what
    really comes out: the sizes in a zip's directory are whatever its maker wrote."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = archive.infolist()
        if len(parts) > MAX_DOCX_PARTS:
            raise ValueError("too many parts")
        total = 0
        for part in parts:
            # Other methods can't be read a little at a time; Word only writes these two.
            if part.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("unexpected compression")
            size = 0
            with archive.open(part) as stream:
                while chunk := stream.read(_READ_CHUNK):
                    size += len(chunk)
                    total += len(chunk)
                    if size > MAX_DOCX_PART_BYTES or total > MAX_DOCX_TOTAL_BYTES:
                        raise ValueError("expands too far")
            if size > DOCX_RATIO_FROM_BYTES and size > MAX_DOCX_RATIO * max(part.compress_size, 1):
                raise ValueError("compressed too tightly")


def _docx(data: bytes) -> str:
    try:
        _check_docx_size(data)
        document = docx.Document(io.BytesIO(data))
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                blocks.append(_paragraph(item))
            elif isinstance(item, Table):
                blocks.append(_table(item))
    # RuntimeError: a password-protected zip. NotImplementedError: a compression zipfile can't read.
    except (
        zipfile.BadZipFile,
        zlib.error,
        EOFError,
        KeyError,
        ValueError,
        RuntimeError,
        NotImplementedError,
    ) as error:
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


# ---------------------------------------------------------------- the child process

_REFUSED_EXIT = 3  # stdout holds the reason, for the parent to pass on


def _limit_memory() -> None:
    try:
        import resource

        with open("/proc/self/statm", encoding="ascii") as statm:
            used = int(statm.read().split()[0]) * resource.getpagesize()
    except (ImportError, OSError):
        return  # shortcut: no cap on Windows and macOS, which only run this in development
    cap = used + ISOLATED_MEMORY_BYTES
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


def _child(fmt: str) -> int:
    _limit_memory()
    try:
        text = file_text(sys.stdin.buffer.read(), fmt)
        if len(text) > MAX_TEXT_CHARS:
            raise ExtractError(TOO_MUCH_TEXT)
    except ExtractError as error:
        sys.stdout.buffer.write(error.reason.encode())
        return _REFUSED_EXIT
    sys.stdout.buffer.write(text.encode())
    return 0


if __name__ == "__main__":
    sys.exit(_child(sys.argv[1]))
