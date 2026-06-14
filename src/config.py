from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "arxiv_papers"
    postgres_user: str
    postgres_password: str

    # OpenSearch
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index_papers: str = "papers"
    opensearch_index_chunks: str = "paper_chunks"

    # Ollama
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    ollama_model: str = "llama3.2"

    # Jina AI
    jina_api_key: str = ""
    jina_model: str = "jina-embeddings-v3"
    embedding_dim: int = 1024

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    cache_ttl_seconds: int = 3600

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # Telegram
    telegram_bot_token: str = ""

    # arXiv
    arxiv_categories: str = "cs.AI,cs.LG,cs.CL"
    arxiv_max_results: int = 50
    arxiv_days_back: int = 7

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
