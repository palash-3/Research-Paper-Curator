import logging
from pathlib import Path

from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)


class PDFParserService:
    """Extracts structured text from a local PDF file using Docling."""

    def __init__(self) -> None:
        self._converter = DocumentConverter()

    def parse(self, pdf_path: Path) -> str | None:
        """
        Parse a local PDF file into markdown text.
        Returns None if parsing fails — not every PDF is parseable
        (scanned images, malformed files, unusual layouts).
        """
        try:
            result = self._converter.convert(str(pdf_path))
            return result.document.export_to_markdown()
        except Exception:
            logger.exception("Docling failed to parse %s", pdf_path)
            return None
