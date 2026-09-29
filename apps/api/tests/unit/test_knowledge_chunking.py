"""T5.3: splitting knowledge into chunks (TR-AI-08): headings and blank lines, chunks of at most
1,200 characters with 150 characters of overlap, the title prefix, and FAQs as one chunk."""

from __future__ import annotations

import itertools
import re

from socialhood.services.knowledge.chunking import (
    CHUNK_CHARS,
    OVERLAP_CHARS,
    faq_text,
    normalise,
    sections,
    split_faq,
    split_text,
    with_title,
)


def numbered_words(start: int, count: int) -> str:
    """Unique words, so an overlap can only be the one the splitter made."""
    return " ".join(f"w{n:05d}" for n in range(start, start + count))


def sentences(start: int, count: int, words: int = 12) -> str:
    return " ".join(numbered_words(start + i * words, words) + "." for i in range(count))


def overlap(previous: str, following: str) -> int:
    """Length of the longest end of ``previous`` that starts ``following``."""
    for n in range(min(len(previous), len(following)), 0, -1):
        if previous.endswith(following[:n]):
            return n
    return 0


def words(text: str) -> list[str]:
    return re.findall(r"w\d{5}", text)


def rejoined(chunks: list[str]) -> list[str]:
    """The words of the chunks with each overlap counted once."""
    out = words(chunks[0])
    for previous, following in itertools.pairwise(chunks):
        out += words(following[overlap(previous, following) :])
    return out


def test_a_short_text_is_one_chunk() -> None:
    assert split_text("We ship across India in 3-5 days.") == ["We ship across India in 3-5 days."]
    assert split_text("   \n\n  ") == []


def test_headings_start_new_chunks_and_a_title_keeps_its_subtitle() -> None:
    text = (
        "# Policies\n## Shipping\nWe ship across India in 3-5 days.\n\n"
        "## Returns\n\nReturns are accepted within 7 days.\n"
        "Intro to payments\n### Payments\nWe accept UPI and cards."
    )
    assert sections(text) == [
        ["# Policies", "## Shipping", "We ship across India in 3-5 days."],
        ["## Returns", "Returns are accepted within 7 days.\nIntro to payments"],
        ["### Payments", "We accept UPI and cards."],
    ]
    assert split_text(text) == [
        "# Policies\n\n## Shipping\n\nWe ship across India in 3-5 days.",
        "## Returns\n\nReturns are accepted within 7 days.\nIntro to payments",
        "### Payments\n\nWe accept UPI and cards.",
    ]


def test_paragraphs_pack_into_chunks_of_at_most_1200_with_150_of_overlap() -> None:
    paragraphs = [sentences(i * 1000, 3, words=10) for i in range(12)]  # ~200 chars each
    text = "\n\n".join(paragraphs)

    chunks = split_text(text)

    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert all(len(c) > CHUNK_CHARS - 250 for c in chunks[:-1])  # packed, not one per paragraph
    for previous, following in itertools.pairwise(chunks):
        assert OVERLAP_CHARS - 10 <= overlap(previous, following) <= OVERLAP_CHARS
        assert re.match(r"w\d{5}", following)  # the overlap starts at a word
    assert rejoined(chunks) == words(text)


def test_a_long_paragraph_splits_at_sentence_ends() -> None:
    text = sentences(0, 40)  # one paragraph of ~3,000 characters

    chunks = split_text(text)

    assert len(chunks) >= 3
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert all(c.endswith(".") for c in chunks)  # cut between sentences
    assert rejoined(chunks) == words(text)


def test_a_sentence_longer_than_a_chunk_splits_between_words() -> None:
    text = numbered_words(0, 500)  # 3,000 characters, no sentence end

    chunks = split_text(text)

    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert all(re.fullmatch(r"w\d{5}( w\d{5})*", c) for c in chunks)  # no word is cut
    assert rejoined(chunks) == words(text)


def test_a_word_longer_than_a_chunk_is_cut() -> None:
    text = "".join(f"{n:04d}" for n in range(750))  # 3,000 characters without a space

    chunks = split_text(text)

    assert len(chunks) == 3
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert "".join(c[overlap(p, c) :] for p, c in zip(["", *chunks], chunks, strict=False)) == text


def test_sections_do_not_overlap_each_other() -> None:
    first = sentences(0, 30)
    second = sentences(5000, 3)
    chunks = split_text(f"# One\n\n{first}\n\n# Two\n\n{second}")

    assert chunks[-1] == f"# Two\n\n{second}"
    assert overlap(chunks[-2], chunks[-1]) == 0


def test_an_faq_is_one_chunk_and_a_long_answer_repeats_the_question() -> None:
    assert split_faq(" Do you ship to Dubai? ", " Yes, in 7 days. ") == [
        "Q: Do you ship to Dubai?\nA: Yes, in 7 days."
    ]
    assert faq_text("Q?", "A.") == "Q: Q?\nA: A."

    answer = sentences(0, 40)
    chunks = split_faq("What are your delivery times?", answer)

    assert len(chunks) > 1
    assert all(c.startswith("Q: What are your delivery times?\nA: ") for c in chunks)
    assert all(len(c) <= CHUNK_CHARS for c in chunks)


def test_the_title_prefix_and_normalising() -> None:
    assert with_title("Shipping", "We ship.") == "[Shipping] We ship."
    assert normalise("a\r\nb  \t c\x00\rd  ") == "a\nb c\nd"
