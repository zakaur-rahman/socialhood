"""Splitting knowledge text into chunks (TR-AI-08).

Text is split into sections at headings (Markdown ``#`` lines; extraction turns Word and web
headings into them) and into paragraphs at blank lines. Each section's paragraphs are packed into
chunks of at most 1,200 characters; a paragraph too long for a chunk is split at sentence ends,
then at spaces. A chunk that continues a section starts with up to the last 150 characters of the
chunk before it (from a word boundary), so a fact cut at a chunk edge is whole in one of them.
Sections never share a chunk, so a chunk is about one heading's topic. Every stored chunk is
prefixed with ``[{source title}] `` (the prefix is not counted in the 1,200).

An FAQ is one chunk, ``Q: …\\nA: …``. An answer too long for one chunk is split, and every part
repeats the question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHUNK_CHARS = 1200
OVERLAP_CHARS = 150

_HEADING = re.compile(r"^ {0,3}#{1,6}\s+\S")
_BLANK_LINES = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?\u3002\uff01\uff1f])\s+")  # also CJK sentence ends
_SPACES = re.compile(r"[ \t\f\v]+")


@dataclass(frozen=True)
class _Piece:
    text: str
    joiner: str  # what goes before it when it follows another piece in a chunk


def normalise(text: str) -> str:
    """Unix newlines, no NULs, no trailing spaces, runs of spaces collapsed."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [_SPACES.sub(" ", line).rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def sections(text: str) -> list[list[str]]:
    """Paragraphs grouped by heading. A heading starts a new section unless the current one
    holds only headings so far (a title followed by a subtitle stays together)."""
    result: list[list[str]] = [[]]
    has_body = False

    def add_heading(line: str) -> None:
        nonlocal has_body
        if has_body:
            result.append([])
            has_body = False
        result[-1].append(line.strip())

    def add_paragraph(lines: list[str]) -> None:
        nonlocal has_body
        paragraph = "\n".join(lines).strip()
        if paragraph:
            result[-1].append(paragraph)
            has_body = True

    for block in _BLANK_LINES.split(normalise(text)):
        lines: list[str] = []
        for line in block.split("\n"):
            if _HEADING.match(line):
                add_paragraph(lines)
                lines = []
                add_heading(line)
            else:
                lines.append(line)
        add_paragraph(lines)
    return [section for section in result if section]


def split_text(text: str, *, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Chunk bodies of at most ``size`` characters, without the title prefix."""
    chunks: list[str] = []
    for section in sections(text):
        chunks.extend(_pack(_pieces(section, size - overlap - 2), size, overlap))
    return chunks


def faq_text(question: str, answer: str) -> str:
    return f"Q: {question.strip()}\nA: {answer.strip()}"


def split_faq(question: str, answer: str, *, size: int = CHUNK_CHARS) -> list[str]:
    """One chunk, or for a long answer several that each repeat the question."""
    whole = faq_text(question, answer)
    if len(whole) <= size:
        return [whole]
    prefix = f"Q: {question.strip()}\nA: "
    room = size - len(prefix)
    parts = split_text(answer, size=room, overlap=min(OVERLAP_CHARS, room // 4))
    return [prefix + part for part in parts]


def with_title(title: str, body: str) -> str:
    return f"[{title}] {body}"


def _pieces(section: list[str], max_piece: int) -> list[_Piece]:
    pieces: list[_Piece] = []
    for paragraph in section:
        for index, part in enumerate(_split_long(paragraph, max_piece)):
            pieces.append(_Piece(part.text, "\n\n" if index == 0 else part.joiner))
    return pieces


def _split_long(paragraph: str, max_piece: int) -> list[_Piece]:
    """A paragraph as pieces of at most ``max_piece``: whole, else by sentence, else by word,
    else cut (a single "word" longer than a chunk)."""
    if len(paragraph) <= max_piece:
        return [_Piece(paragraph, "\n\n")]
    pieces: list[_Piece] = []
    for sentence in _SENTENCE_END.split(paragraph):
        if len(sentence) <= max_piece:
            pieces.append(_Piece(sentence, " "))
            continue
        for word in re.split(r"(?<=\S)\s+(?=\S)", sentence):
            if len(word) <= max_piece:
                pieces.append(_Piece(word, " "))
                continue
            for start in range(0, len(word), max_piece):
                pieces.append(_Piece(word[start : start + max_piece], "" if start else " "))
    return _merge(pieces, max_piece)


def _merge(pieces: list[_Piece], max_piece: int) -> list[_Piece]:
    """Join neighbouring small pieces back together while they fit, so words become sentences
    again and sentences become pieces near ``max_piece``."""
    merged: list[_Piece] = []
    for piece in pieces:
        if merged and len(merged[-1].text) + len(piece.joiner) + len(piece.text) <= max_piece:
            last = merged[-1]
            merged[-1] = _Piece(last.text + piece.joiner + piece.text, last.joiner)
        else:
            merged.append(piece)
    return merged


def _pack(pieces: list[_Piece], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece.text
            continue
        candidate = current + piece.joiner + piece.text
        if len(candidate) <= size:
            current = candidate
            continue
        chunks.append(current)
        tail = _tail(current, overlap)
        current = tail + (piece.joiner or "") + piece.text if tail else piece.text
    if current:
        chunks.append(current)
    return chunks


def _tail(text: str, overlap: int) -> str:
    """Up to the last ``overlap`` characters of ``text``, starting at a word."""
    if overlap <= 0:
        return ""
    tail = text[-overlap:]
    starts_mid_word = len(text) > overlap and not text[-overlap - 1].isspace()
    if starts_mid_word and not tail[0].isspace():
        cut = re.search(r"\s", tail)
        if cut is not None:
            tail = tail[cut.start() :]
    return tail.strip()
