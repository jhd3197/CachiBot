"""Test PDF text extraction with and without fontTools."""

from pathlib import Path

import pymupdf
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURE_DIR / "sample.pdf"


@pytest.fixture(autouse=True)
def ensure_fixture():
    """Create a minimal PDF fixture if it doesn't exist."""
    FIXTURE_DIR.mkdir(exist_ok=True)
    if not SAMPLE_PDF.exists():
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello, CachiBot!")
        doc.save(str(SAMPLE_PDF))
        doc.close()


def test_pdf_extraction_basic():
    doc = pymupdf.open(str(SAMPLE_PDF))
    text = "".join(page.get_text() for page in doc)
    doc.close()
    assert "Hello, CachiBot!" in text
