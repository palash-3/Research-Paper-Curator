import gc
import logging

from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.services.arxiv_client import ArxivClient
from src.services.pdf_downloader import download_pdf
from src.services.pdf_parser import PDFParserService

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """Orchestrates: fetch from arXiv -> download PDF -> parse -> store in Postgres."""

    def __init__(
        self, db: Session, arxiv_client: ArxivClient, pdf_parser: PDFParserService
    ) -> None:
        self.db = db
        self.arxiv_client = arxiv_client
        self.pdf_parser = pdf_parser

    def run(self, days_back: int = 7) -> dict:
        """
        Fetch recent papers from arXiv, skip ones already stored,
        download + parse PDFs for new ones, and save to PostgreSQL.
        """
        papers = self.arxiv_client.fetch_recent_papers(days_back)
        saved = 0
        skipped = 0
        failed = 0

        for arxiv_paper in papers:
            arxiv_id = arxiv_paper.get_short_id()
            existing = self.db.get(Paper, arxiv_id)
            if existing:
                skipped += 1
                continue

            pdf_url = arxiv_paper.pdf_url or ""
            local_pdf_path = download_pdf(pdf_url, arxiv_id)

            full_text = None
            if local_pdf_path is not None:
                full_text = self.pdf_parser.parse(local_pdf_path)

            paper = Paper(
                id=arxiv_id,
                title=arxiv_paper.title,
                abstract=arxiv_paper.summary,
                full_text=full_text,
                authors=str([a.name for a in arxiv_paper.authors]),
                categories=",".join(arxiv_paper.categories),
                published_date=arxiv_paper.published,
                pdf_url=pdf_url,
            )

            try:
                self.db.add(paper)
                self.db.commit()
                saved += 1
            except Exception:
                self.db.rollback()
                logger.exception("Failed to save paper %s", arxiv_id)
                failed += 1
            finally:
                del full_text
                gc.collect()

        return {"saved": saved, "skipped": skipped, "failed": failed}
