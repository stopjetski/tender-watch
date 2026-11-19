"""PDF text, downloaded once and kept.

Each PDF is saved under cache/pdf/ by the hash of its address, with the
extracted text beside it, so a later run never fetches or reads it again.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from pypdf import PdfReader

CACHE_DIR = Path("cache/pdf")
MIN_CHARS_PER_PAGE = 40  # fewer than this and the PDF is probably a scan


def extract_text(data: bytes) -> tuple[str, list[str]]:
    """Return (text, notes). A scanned PDF gives little or no text; the note says so."""
    notes = []
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(pages).strip()
    if not pages:
        notes.append("PDF has no pages")
    elif len(text) < MIN_CHARS_PER_PAGE * len(pages):
        notes.append("PDF has almost no text; it is probably a scanned image and needs OCR")
    return text, notes


class PdfCache:
    def __init__(self, session, directory: Path = CACHE_DIR):
        self.session = session
        self.directory = directory
        self.downloads = 0

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{key}.pdf", self.directory / f"{key}.txt"

    def text(self, url: str) -> tuple[str, list[str]]:
        pdf_path, text_path = self._paths(url)
        if not pdf_path.exists():
            response = self.session.get(url)
            self.directory.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(response.content)
            self.downloads += 1
        if text_path.exists():
            return text_path.read_text(encoding="utf-8"), []
        try:
            text, notes = extract_text(pdf_path.read_bytes())
        except Exception as error:  # noqa: BLE001 - a broken PDF is logged, not fatal
            return "", [f"PDF could not be read: {error}"]
        if not notes:
            text_path.write_text(text, encoding="utf-8")
        return text, notes
