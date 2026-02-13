from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Base class for all data collectors."""

    DEFAULT_HEADERS = {
        "User-Agent": "PharmaCI-Tool/1.0",
    }

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    @abstractmethod
    def collect(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """
        Collect data based on query.

        Args:
            query: Search term (drug name, indication, etc.)
            **kwargs: Additional parameters

        Returns:
            List of collected data records
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this data source."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: dict | None = None,
        headers: dict | None = None,
        json_data: dict | None = None,
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
            url: Request URL
            method: HTTP method
            params: Query parameters
            headers: Request headers
            json_data: JSON body for POST requests

        Returns:
            HTTP response
        """
        logger.debug(f"Making {method} request to {url}")
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json_data,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _parse_date(self, date_str: str | None, formats: list[str] | None = None) -> datetime | None:
        """
        Parse date string to datetime.

        Args:
            date_str: Date string to parse
            formats: List of date formats to try

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        if formats is None:
            formats = [
                "%Y-%m-%d",
                "%Y-%m",
                "%Y",
                "%B %d, %Y",
                "%b %d, %Y",
                "%d %B %Y",
                "%m/%d/%Y",
            ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
