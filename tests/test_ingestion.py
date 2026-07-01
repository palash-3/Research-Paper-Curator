from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.arxiv_client import ArxivClient
from src.services.metadata_fetcher import MetadataFetcher
from src.services.pdf_downloader import download_pdf


class TestArxivClient:
    """Unit tests for ArxivClient — no real network calls."""

    @patch("src.services.arxiv_client.arxiv.Client")
    def test_fetch_filters_by_date(self, mock_client_class):
        """Papers older than the cutoff should be excluded."""
        # Arrange: create two fake papers — one recent, one old
        from datetime import timedelta

        now = datetime.now(tz=UTC)

        recent_paper = MagicMock()
        recent_paper.published = now - timedelta(days=2)  # 2 days ago — within window
        recent_paper.get_short_id.return_value = "2506.12345v1"

        old_paper = MagicMock()
        old_paper.published = now - timedelta(days=30)  # 30 days ago — outside window
        old_paper.get_short_id.return_value = "2401.99999v1"

        # Make the fake client return these two papers
        mock_instance = MagicMock()
        mock_instance.results.return_value = iter([recent_paper, old_paper])
        mock_client_class.return_value = mock_instance

        # Act
        client = ArxivClient()
        papers = client.fetch_recent_papers(days_back=7)

        # Assert: only the recent paper should survive the date filter
        assert len(papers) == 1
        assert papers[0] == recent_paper

    @patch("src.services.arxiv_client.arxiv.Client")
    def test_fetch_returns_partial_on_error(self, mock_client_class):
        """If the connection drops mid-fetch, return whatever was collected."""
        from datetime import timedelta

        now = datetime.now(tz=UTC)

        good_paper = MagicMock()
        good_paper.published = now - timedelta(days=1)

        # Simulate: yield one paper, then raise an exception
        def exploding_generator():
            yield good_paper
            raise ConnectionError("network dropped")

        mock_instance = MagicMock()
        mock_instance.results.return_value = exploding_generator()
        mock_client_class.return_value = mock_instance

        # Act
        client = ArxivClient()
        papers = client.fetch_recent_papers(days_back=7)

        # Assert: should have the one paper collected before the crash
        assert len(papers) == 1
        assert papers[0] == good_paper


class TestPDFDownloader:
    """Unit tests for download_pdf — no real network calls."""

    @patch("src.services.pdf_downloader.httpx.get")
    def test_download_saves_file(self, mock_get, tmp_path):
        """A successful download should save the PDF to disk."""
        # Arrange: fake a successful HTTP response with some bytes
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 fake pdf content"
        mock_response.raise_for_status = MagicMock()  # no error
        mock_get.return_value = mock_response

        # Override the cache dir to use pytest's tmp_path (clean, isolated)
        with patch("src.services.pdf_downloader.PDF_CACHE_DIR", tmp_path):
            result = download_pdf("https://arxiv.org/pdf/2401.12345", "2401.12345")

        # Assert
        assert result is not None
        assert result.exists()
        assert result.name == "2401.12345.pdf"
        assert result.read_bytes() == b"%PDF-1.4 fake pdf content"

    @patch("src.services.pdf_downloader.httpx.get")
    def test_download_cache_hit(self, mock_get, tmp_path):
        """If the file already exists, skip the download entirely."""
        # Arrange: pre-create the file
        cached_file = tmp_path / "2401.12345.pdf"
        cached_file.write_bytes(b"already here")

        with patch("src.services.pdf_downloader.PDF_CACHE_DIR", tmp_path):
            result = download_pdf("https://arxiv.org/pdf/2401.12345", "2401.12345")

        # Assert: got the cached path back, and httpx was NEVER called
        assert result == cached_file
        mock_get.assert_not_called()

    @patch("src.services.pdf_downloader.httpx.get")
    def test_download_failure_returns_none(self, mock_get, tmp_path):
        """A network error should return None, not crash."""
        mock_get.side_effect = Exception("connection refused")

        with patch("src.services.pdf_downloader.PDF_CACHE_DIR", tmp_path):
            result = download_pdf("https://arxiv.org/pdf/bad", "bad-id")

        assert result is None


class TestMetadataFetcher:
    """Unit tests for MetadataFetcher — all dependencies mocked."""

    def _make_fake_paper(self, arxiv_id="2506.12345v1"):
        """Helper: build a fake arxiv.Result with all the fields MetadataFetcher reads."""
        from datetime import timedelta

        paper = MagicMock()
        paper.get_short_id.return_value = arxiv_id
        paper.title = "Fake Paper Title"
        paper.summary = "This is a fake abstract."
        paper.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        paper.authors = [MagicMock(name="Author One"), MagicMock(name="Author Two")]
        paper.categories = ["cs.AI", "cs.LG"]
        paper.published = datetime.now(tz=UTC) - timedelta(days=1)
        return paper

    @patch("src.services.metadata_fetcher.download_pdf")
    def test_new_paper_saved(self, mock_download):
        """A brand new paper should be downloaded, parsed, and saved."""
        # Arrange
        fake_paper = self._make_fake_paper()
        mock_download.return_value = Path("/tmp/fake.pdf")

        mock_db = MagicMock()
        mock_db.get.return_value = None  # not in DB yet

        mock_arxiv = MagicMock()
        mock_arxiv.fetch_recent_papers.return_value = [fake_paper]

        mock_parser = MagicMock()
        mock_parser.parse.return_value = "# Introduction\nSome parsed text."

        # Act
        fetcher = MetadataFetcher(db=mock_db, arxiv_client=mock_arxiv, pdf_parser=mock_parser)
        result = fetcher.run(days_back=7)

        # Assert
        assert result["saved"] == 1
        assert result["skipped"] == 0
        assert result["failed"] == 0
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("src.services.metadata_fetcher.download_pdf")
    def test_existing_paper_skipped(self, mock_download):
        """A paper already in the DB should be skipped — no download, no parse."""
        fake_paper = self._make_fake_paper()

        mock_db = MagicMock()
        mock_db.get.return_value = MagicMock()  # already exists

        mock_arxiv = MagicMock()
        mock_arxiv.fetch_recent_papers.return_value = [fake_paper]

        mock_parser = MagicMock()

        fetcher = MetadataFetcher(db=mock_db, arxiv_client=mock_arxiv, pdf_parser=mock_parser)
        result = fetcher.run(days_back=7)

        assert result["skipped"] == 1
        assert result["saved"] == 0
        mock_download.assert_not_called()
        mock_parser.parse.assert_not_called()

    @patch("src.services.metadata_fetcher.download_pdf")
    def test_download_failure_still_saves(self, mock_download):
        """If PDF download fails, save the paper anyway (with no full_text)."""
        fake_paper = self._make_fake_paper()
        mock_download.return_value = None  # download failed

        mock_db = MagicMock()
        mock_db.get.return_value = None

        mock_arxiv = MagicMock()
        mock_arxiv.fetch_recent_papers.return_value = [fake_paper]

        mock_parser = MagicMock()

        fetcher = MetadataFetcher(db=mock_db, arxiv_client=mock_arxiv, pdf_parser=mock_parser)
        result = fetcher.run(days_back=7)

        # Paper saved, but parser was never called (nothing to parse)
        assert result["saved"] == 1
        mock_parser.parse.assert_not_called()
        mock_db.add.assert_called_once()
