import pytest

from app.services.pdf import count_pdf_pages


def test_pdf_pages_real_file(tmp_path):
    """Use a tiny generated PDF. PyPDF2 round-trips this."""
    from PyPDF2 import PdfWriter

    p = tmp_path / "x.pdf"
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    w.add_blank_page(width=100, height=100)
    with open(p, "wb") as fh:
        w.write(fh)
    assert count_pdf_pages(str(p)) == 2


def test_unknown_file_returns_zero(tmp_path):
    p = tmp_path / "junk"
    p.write_bytes(b"not-a-pdf")
    assert count_pdf_pages(str(p)) == 0
