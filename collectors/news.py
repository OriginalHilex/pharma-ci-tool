from typing import Any
from datetime import datetime
import logging
from urllib.parse import quote_plus
import feedparser
from .base import BaseCollector
from config import settings
from config.search_config import AssetConfig, DiseaseConfig

logger = logging.getLogger(__name__)


class NewsCollector(BaseCollector):
    """Collector for Google News via RSS feeds."""

    def __init__(self):
        super().__init__()
        self.base_url = settings.google_news_rss_url

    def get_source_name(self) -> str:
        return "Google News"

    def collect(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """
        Collect news articles matching the query.

        Args:
            query: Search term (drug name, company name, etc.)
            **kwargs:
                - max_results: Maximum number of results (default 50)
                - language: Language code (default 'en')
                - region: Region code (default 'US')

        Returns:
            List of news article records
        """
        max_results = kwargs.get("max_results", 50)
        language = kwargs.get("language", "en")
        region = kwargs.get("region", "US")

        # Build RSS URL with query
        encoded_query = quote_plus(query)
        rss_url = f"{self.base_url}?q={encoded_query}&hl={language}-{region}&gl={region}&ceid={region}:{language}"

        articles = []

        try:
            # Fetch RSS feed
            response = self._make_request(rss_url)
            feed = feedparser.parse(response.text)

            for entry in feed.entries[:max_results]:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)

        except Exception as e:
            logger.error(f"Error collecting news for '{query}': {e}")

        logger.info(f"Collected {len(articles)} news articles for query: {query}")
        return articles

    def collect_by_asset(self, asset: AssetConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Asset monitoring with aliases.

        Builds an OR query from all asset aliases with pharma context.
        """
        # Quote each alias and OR them together
        alias_parts = []
        for alias in asset.aliases:
            alias_parts.append(f'"{alias}"')
        aliases_query = " OR ".join(alias_parts)

        query = f'({aliases_query}) AND (pharma OR clinical OR FDA OR trial)'
        logger.info(f"News asset query: {query}")
        return self.collect(query, **kwargs)

    def collect_by_disease(
        self,
        disease: DiseaseConfig,
        discovery_keywords: list[str],
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Disease discovery monitoring.

        Combines disease aliases with competitor/pipeline/approval keywords.
        """
        alias_parts = []
        for alias in disease.aliases:
            if " " in alias:
                alias_parts.append(f'"{alias}"')
            else:
                alias_parts.append(alias)
        disease_query = " OR ".join(alias_parts)

        keywords_query = " OR ".join(discovery_keywords)

        query = f'({disease_query}) AND ({keywords_query})'
        logger.info(f"News disease discovery query: {query}")
        return self.collect(query, **kwargs)

    def _parse_entry(self, entry: Any) -> dict[str, Any] | None:
        """Parse a single RSS entry."""
        try:
            # Parse title (often includes source in brackets)
            title = entry.get("title", "")
            source = None

            # Extract source from title if present (format: "Title - Source")
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title = parts[0]
                    source = parts[1]

            # Parse published date
            published_at = None
            published_str = entry.get("published")
            if published_str:
                try:
                    # feedparser often provides parsed date
                    published_parsed = entry.get("published_parsed")
                    if published_parsed:
                        published_at = datetime(*published_parsed[:6])
                    else:
                        published_at = self._parse_date(published_str)
                except Exception:
                    pass

            # Get URL (Google News redirects through their service)
            url = entry.get("link", "")

            # Get summary/description
            summary = entry.get("summary", "") or entry.get("description", "")
            # Clean HTML tags from summary
            if summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary)

            if not url or not title:
                return None

            return {
                "title": title.strip(),
                "source": source,
                "published_at": published_at,
                "url": url,
                "summary": summary.strip() if summary else None,
                "sentiment_score": None,
            }

        except Exception as e:
            logger.error(f"Error parsing news entry: {e}")
            return None

    def collect_for_drug(self, drug_name: str, **kwargs) -> list[dict[str, Any]]:
        """Collect news specifically about a drug (legacy method)."""
        query = f'"{drug_name}" pharma OR clinical OR FDA'
        return self.collect(query, **kwargs)

    def collect_for_company(self, company_name: str, **kwargs) -> list[dict[str, Any]]:
        """Collect news about a pharmaceutical company (legacy method)."""
        query = f'"{company_name}" pharmaceutical OR biotech OR drug'
        return self.collect(query, **kwargs)
