from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql://localhost/ci_tool",
        description="PostgreSQL connection string"
    )

    # NCBI/PubMed
    ncbi_api_key: str | None = Field(
        default=None,
        description="NCBI API key for higher rate limits"
    )

    # Application
    log_level: str = Field(default="INFO")
    collection_interval_hours: int = Field(
        default=24,
        description="Hours between data collection runs"
    )

    # Search configuration
    search_config_path: str | None = Field(
        default=None,
        description="Path to search_config.yaml (defaults to config/search_config.yaml)"
    )

    # API Endpoints
    clinicaltrials_api_url: str = "https://clinicaltrials.gov/api/v2"
    pubmed_api_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    google_news_rss_url: str = "https://news.google.com/rss/search"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
