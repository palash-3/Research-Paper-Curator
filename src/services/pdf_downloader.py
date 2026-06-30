import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PDF_CACHE_DIR = Path("data/pdfs")
PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def download_pdf(pdf_url: str, arxiv_id: str) -> Path | None:
    """
    Download a PDF from arXiv to the local cache, unless it's already
    cached. Returns the local file path, or None if the download fails.
    """

    local_path = PDF_CACHE_DIR / f"{arxiv_id}.pdf"

    if local_path.exists():
        logger.info("Cache hit: %s already downloaded", arxiv_id)
        return local_path
    try:
        response = httpx.get(pdf_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to download PDF for %s", arxiv_id)
        return None

    local_path.write_bytes(response.content)
    logger.info("Downloaded and cached: %s", arxiv_id)
    return local_path
