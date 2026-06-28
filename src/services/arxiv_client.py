# src/services/arxiv_client.py
"""
Client for fetching paper metadata from the arXiv API.

arXiv's API enforces a soft rate limit: no more than 1 request every
3 seconds per IP. We rely on the `arxiv` library's built-in
`delay_seconds` to enforce this — we do NOT also sleep manually,
since that would double the wait for no benefit.
"""

import logging
from datetime import datetime, timedelta

import arxiv

from src.config import settings

logger = logging.getLogger(__name__)


class ArxivClient:
    """Thin wrapper around the `arxiv` package with retry + date filtering."""

    RATE_LIMIT_SECONDS = 3.0
    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._client = arxiv.Client(
            delay_seconds=self.RATE_LIMIT_SECONDS,
            num_retries=self.MAX_RETRIES,
        )

    def fetch_recent_papers(self, days_back: int = 7) -> list[arxiv.Result]:
        """
        Fetch papers from the configured categories published in the
        last `days_back` days, newest first.
        """
        categories = settings.arxiv_categories.split(",")
        query = " OR ".join(f"cat:{c.strip()}" for c in categories)

        search = arxiv.Search(
            query=query,
            max_results=settings.arxiv_max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        cutoff = datetime.now() - timedelta(days=days_back)
        papers: list[arxiv.Result] = []

        try:
            for result in self._client.results(search):
                published_naive = result.published.replace(tzinfo=None)
                if published_naive < cutoff:
                    # Results are sorted newest-first, so once we hit
                    # something older than the cutoff, everything after
                    # is also too old — safe to stop early.
                    break
                papers.append(result)
        except Exception:
            # Log and return whatever we already collected, rather than
            # losing an entire day's run because the connection dropped
            # partway through.
            logger.exception("arXiv fetch interrupted after %d papers", len(papers))

        logger.info("Fetched %d papers from arXiv (days_back=%d)", len(papers), days_back)
        return papers
