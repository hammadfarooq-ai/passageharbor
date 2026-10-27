"""Text-only PDF extraction, shared by the UI and the original page-file CLI."""

import argparse
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pypdf import PdfReader

Progress = Callable[[str, float], None]


class PDFError(ValueError):
    """A PDF cannot be processed; the message is safe to show to the user."""


@dataclass(frozen=True)
class Page:
    number: int
    text: str


@dataclass
class Extraction:
    pages: list[Page]
    empty_pages: list[int]


def extract_pdf_bytes(data: bytes, max_upload_mb: int = 25,
                      progress: Progress | None = None) -> Extraction:
    if not data:
        raise PDFError("The PDF is empty. Choose a file containing text.")
    if len(data) > max_upload_mb * 1024 * 1024:
        raise PDFError(f"The PDF exceeds the {max_upload_mb} MB upload limit.")
    if b"%PDF-" not in data[:1024]:
        raise PDFError("This file is not a readable PDF. Choose a valid PDF file.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                opened = reader.decrypt("")
            except Exception:
                opened = False
            if not opened:
                raise PDFError("This PDF is password protected. Save an unlocked copy first.")
        if not reader.pages:
            raise PDFError("This PDF has no pages.")
        pages, empty = [], []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(Page(number, text))
            if not any(c.isalnum() for c in text):
                empty.append(number)
            if progress:
                progress("Extracting PDF pages", number / len(reader.pages))
    except PDFError:
        raise
    except Exception:
        raise PDFError("The PDF could not be read. It may be corrupt or use unsupported encryption.") from None
    if len(empty) == len(pages):
        raise PDFError("No useful text could be extracted. Scanned PDFs need an OCR step before upload; this app does not perform OCR.")
    return Extraction(pages, empty)


def extract_pdf_to_txt(pdf_path: str, output_dir: str = "output_text",
                       max_upload_mb: int = 25):
    """Keep the existing page_1.txt, page_2.txt extraction workflow."""
    result = extract_pdf_bytes(Path(pdf_path).read_bytes(), max_upload_mb)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for page in result.pages:
        target = output / f"page_{page.number}.txt"
        target.write_text(page.text, encoding="utf-8")
        print(f"Extracted page {page.number} to {target}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract a text PDF into page_*.txt files.")
    parser.add_argument("pdf", nargs="?", default="Think-And-Grow-Rich_2011-06.pdf")
    parser.add_argument("--output-dir", default="output_text")
    args = parser.parse_args()
    try:
        extract_pdf_to_txt(args.pdf, args.output_dir)
    except (PDFError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
