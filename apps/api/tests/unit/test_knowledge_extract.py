"""T5.3: text from knowledge files and web pages (TR-AI-08, FR-KB-01): PDF by pypdf, DOCX by
python-docx (headings kept for chunking), TXT and MD as text; failures in plain words. Uploads
for knowledge are limited to those formats, up to 10 MB, when they are registered."""

from __future__ import annotations

import uuid

import pytest

from socialhood.errors import ApiError
from socialhood.media.cloudinary import StoredResource
from socialhood.services import media_assets
from socialhood.services.knowledge.chunking import split_text
from socialhood.services.knowledge.extract import ExtractError, file_text, web_page
from tests.support.knowledge import make_docx, make_pdf


def test_pdf_text_is_extracted_page_by_page() -> None:
    data = make_pdf(
        ["Shipping policy", "We ship across India in 3-5 days."],
        ["International", "We ship to the UAE in 7-10 days (Rs 1,500)."],
    )

    text = file_text(data, "PDF")

    assert "We ship across India in 3-5 days." in text
    assert "We ship to the UAE in 7-10 days (Rs 1,500)." in text
    assert text.index("Shipping policy") < text.index("International")


def test_a_pdf_without_text_or_a_broken_one_fails_plainly() -> None:
    with pytest.raises(ExtractError, match="Scanned PDFs"):
        file_text(make_pdf([]), "pdf")
    with pytest.raises(ExtractError, match="Couldn't read this PDF"):
        file_text(b"%PDF-1.7 this is not really a pdf", "pdf")


def test_docx_headings_paragraphs_and_tables() -> None:
    data = make_docx(
        [
            ("h1", "Shipping"),
            ("p", "We ship across India in 3-5 days."),
            ("h1", "Returns"),
            ("p", "Returns are accepted within 7 days."),
        ],
        table=[["Zone", "Days"], ["UAE", "7-10"]],
    )

    text = file_text(data, "docx")

    assert text == (
        "# Shipping\n\nWe ship across India in 3-5 days.\n\n# Returns\n\n"
        "Returns are accepted within 7 days.\n\nZone | Days\nUAE | 7-10"
    )
    assert split_text(text) == [
        "# Shipping\n\nWe ship across India in 3-5 days.",
        "# Returns\n\nReturns are accepted within 7 days.\n\nZone | Days\nUAE | 7-10",
    ]


def test_a_broken_docx_fails_plainly() -> None:
    with pytest.raises(ExtractError, match="Word document"):
        file_text(b"PK\x03\x04 not a zip", "docx")


def test_text_and_markdown_files() -> None:
    assert file_text("﻿Prices start at ₹499.\r\n".encode(), "txt") == "Prices start at ₹499."
    assert file_text(b"# FAQ\n\nWe open at 9.", "md") == "# FAQ\n\nWe open at 9."
    assert file_text("Caf\xe9 hours".encode("cp1252"), "txt") == "Café hours"
    with pytest.raises(ExtractError, match="no text"):
        file_text(b"  \n ", "txt")
    with pytest.raises(ExtractError, match="PDF, Word"):
        file_text(b"x", "xlsx")


def test_a_web_page_keeps_its_main_text_headings_and_title() -> None:
    html = b"""<html><head><title>Shipping | Maple Bakery</title></head><body>
    <nav>Home Shop Contact</nav>
    <article><h1>Shipping policy</h1>
    <p>We ship across India in 3-5 days. Orders over Rs 999 ship free of charge.</p>
    <p>Every cake is packed in a cool box, and we send a tracking link by SMS once your parcel
    leaves our kitchen in Pune. Deliveries arrive between 10 am and 7 pm, Monday to Saturday.</p>
    <h2>International</h2>
    <p>We ship to the UAE and Singapore. Delivery takes 7-10 days and costs Rs 1,500.</p>
    <p>International orders ship dry cakes and cookies only, because fresh cream cannot travel
    that far. Customs duties, if any, are paid by the customer on delivery.</p>
    </article><footer>Copyright Maple Bakery</footer></body></html>"""

    page = web_page(html, "https://maple.example/shipping")

    assert page.title == "Shipping policy"  # trafilatura prefers the page heading
    assert "## International" in page.text
    assert "We ship to the UAE and Singapore." in page.text
    assert "Copyright" not in page.text


def test_a_page_without_readable_text_fails() -> None:
    with pytest.raises(ExtractError, match="readable text"):
        web_page(b"<html><body><script>var a = 1;</script></body></html>")


@pytest.mark.parametrize(
    ("fmt", "size", "accepted"),
    [
        ("pdf", 10 * 1024 * 1024, True),
        ("docx", 1000, True),
        ("txt", 10, True),
        ("md", 10, True),
        ("pdf", 10 * 1024 * 1024 + 1, False),
        ("xlsx", 1000, False),
        ("doc", 1000, False),
        ("jpg", 1000, False),
    ],
)
def test_knowledge_uploads_are_checked_when_registered(fmt: str, size: int, accepted: bool) -> None:
    resource = StoredResource(
        public_id=f"ws/{uuid.uuid4()}/knowledge/abc.{fmt}",
        resource_type="raw",
        format=None,
        secure_url=f"https://res.cloudinary.com/demo/raw/upload/abc.{fmt}",
        bytes=size,
    )
    if accepted:
        assert media_assets.check_limits(resource, "knowledge") is media_assets.KNOWLEDGE_FILE
        return
    with pytest.raises(ApiError) as caught:
        media_assets.check_limits(resource, "knowledge")
    assert caught.value.code == "unsupported_media"
