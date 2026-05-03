def count_pdf_pages(file_path: str) -> int:
    try:
        from PyPDF2 import PdfReader

        return len(PdfReader(file_path).pages)
    except Exception:
        return 0
