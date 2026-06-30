from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="arxiv_paper_ingestion",
    schedule="0 6 * * 1-5",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
)
def arxiv_ingestion():
    @task
    def fetch_and_store() -> dict:
        from src.config import settings
        from src.services.arxiv_client import ArxivClient
        from src.services.database import SessionLocal
        from src.services.metadata_fetcher import MetadataFetcher
        from src.services.pdf_parser import PDFParserService

        db = SessionLocal()
        try:
            fetcher = MetadataFetcher(
                db=db,
                arxiv_client=ArxivClient(),
                pdf_parser=PDFParserService(),
            )
            result = fetcher.run(days_back=settings.arxiv_days_back)
        finally:
            db.close()

        print(f"Ingestion complete: {result}")
        return result

    fetch_and_store()


arxiv_ingestion()
