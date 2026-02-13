from typing import Any
from datetime import datetime, timedelta
import logging
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from .base import BaseCollector
from config.search_config import AssetConfig, DiseaseConfig

logger = logging.getLogger(__name__)


class PatentsCollector(BaseCollector):
    """Collector for Google Patents via web scraping."""

    def __init__(self):
        super().__init__(timeout=60.0)  # Patents pages can be slow
        self.base_url = "https://patents.google.com"

    def get_source_name(self) -> str:
        return "Google Patents"

    def collect(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """
        Collect patents matching the query.

        Args:
            query: Search term (drug name, mechanism, company, etc.)
            **kwargs:
                - max_results: Maximum number of results (default 20)
                - assignee: Filter by patent assignee/company
                - after_date: Only patents after this date (datetime or str YYYY-MM-DD)
                - recent_days: Shortcut — only patents from the last N days (default: None)

        Returns:
            List of patent records
        """
        max_results = kwargs.get("max_results", 20)
        assignee = kwargs.get("assignee")
        after_date = kwargs.get("after_date")
        recent_days = kwargs.get("recent_days")

        # Build search query
        search_query = query

        if assignee:
            search_query = f'{search_query} assignee:"{assignee}"'

        # Date filtering via Google Patents query syntax
        if recent_days and not after_date:
            after_date = (datetime.utcnow() - timedelta(days=recent_days)).strftime("%Y-%m-%d")
        if after_date:
            if isinstance(after_date, datetime):
                after_date = after_date.strftime("%Y-%m-%d")
            search_query = f'{search_query} after:{after_date}'

        encoded_query = quote_plus(search_query)
        search_url = f"{self.base_url}/?q={encoded_query}&oq={encoded_query}"

        patents = []

        try:
            response = self._make_request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            )
            patents = self._parse_search_results(response.text, max_results)

        except Exception as e:
            logger.error(f"Error collecting patents for '{query}': {e}")

        logger.info(f"Collected {len(patents)} patents for query: {query}")
        return patents

    def collect_by_asset(self, asset: AssetConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Asset-specific patent monitoring with aliases.

        Builds an OR query from all asset aliases.
        """
        query = asset.or_query()
        logger.info(f"Patents asset query: {query}")
        return self.collect(query, **kwargs)

    def collect_by_disease(self, disease: DiseaseConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Disease-linked patent monitoring.

        Builds an OR query from disease aliases.
        """
        query = disease.or_query()
        logger.info(f"Patents disease query: {query}")
        return self.collect(query, **kwargs)

    def _parse_search_results(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Parse patent search results from HTML."""
        patents = []
        soup = BeautifulSoup(html, "lxml")

        # Find patent result items
        results = soup.find_all("article", class_="result")
        if not results:
            # Try alternative selector
            results = soup.find_all("search-result-item")

        for result in results[:max_results]:
            patent = self._parse_result_item(result)
            if patent:
                patents.append(patent)

        return patents

    def _parse_result_item(self, item) -> dict[str, Any] | None:
        """Parse a single patent result item."""
        try:
            # Extract patent number
            patent_link = item.find("a", {"data-result": True})
            if not patent_link:
                patent_link = item.find("a", href=re.compile(r"/patent/"))

            if not patent_link:
                return None

            href = patent_link.get("href", "")
            patent_number = None

            # Extract patent number from URL
            match = re.search(r"/patent/([A-Z0-9]+)", href)
            if match:
                patent_number = match.group(1)
            else:
                return None

            # Title
            title_elem = item.find("h3") or item.find("span", class_="title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Assignee
            assignee = None
            assignee_elem = item.find("span", {"data-assignee": True})
            if not assignee_elem:
                assignee_elem = item.find(string=re.compile(r"Assignee"))
                if assignee_elem:
                    assignee = assignee_elem.find_next("span")
            if assignee_elem:
                assignee = assignee_elem.get_text(strip=True) if hasattr(assignee_elem, 'get_text') else str(assignee_elem)

            # Dates
            filing_date = None
            grant_date = None

            date_elems = item.find_all("span", class_="date")
            for date_elem in date_elems:
                date_text = date_elem.get_text(strip=True)
                date_value = self._parse_date(date_text)
                if date_value:
                    # Heuristic: earlier date is filing, later is grant
                    if not filing_date:
                        filing_date = date_value
                    else:
                        grant_date = date_value

            # Abstract (usually not in search results, would need detail page)
            abstract = None
            abstract_elem = item.find("span", class_="abstract")
            if abstract_elem:
                abstract = abstract_elem.get_text(strip=True)

            return {
                "patent_number": patent_number,
                "title": title,
                "assignee": assignee,
                "filing_date": filing_date,
                "grant_date": grant_date,
                "abstract": abstract,
                "claims_count": None,  # Would require detail page
                "source_url": f"{self.base_url}/patent/{patent_number}",
            }

        except Exception as e:
            logger.error(f"Error parsing patent result: {e}")
            return None

    def fetch_patent_details(self, patent_number: str) -> dict[str, Any] | None:
        """Fetch detailed information for a specific patent."""
        url = f"{self.base_url}/patent/{patent_number}"

        try:
            response = self._make_request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            )
            return self._parse_patent_detail(response.text, patent_number)
        except Exception as e:
            logger.error(f"Error fetching patent details for {patent_number}: {e}")
            return None

    def _parse_patent_detail(self, html: str, patent_number: str) -> dict[str, Any] | None:
        """Parse patent detail page."""
        soup = BeautifulSoup(html, "lxml")

        try:
            # Title
            title_elem = soup.find("h1", id="title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Abstract
            abstract_elem = soup.find("div", class_="abstract")
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else None

            # Claims count
            claims_count = None
            claims_section = soup.find("section", id="claims")
            if claims_section:
                claims = claims_section.find_all("div", class_="claim")
                claims_count = len(claims)

            # Assignee and dates from metadata table
            assignee = None
            filing_date = None
            grant_date = None

            meta_table = soup.find("table", class_="metadata")
            if meta_table:
                rows = meta_table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        if "assignee" in label:
                            assignee = value
                        elif "filing" in label:
                            filing_date = self._parse_date(value)
                        elif "grant" in label or "publication" in label:
                            grant_date = self._parse_date(value)

            return {
                "patent_number": patent_number,
                "title": title,
                "assignee": assignee,
                "filing_date": filing_date,
                "grant_date": grant_date,
                "abstract": abstract,
                "claims_count": claims_count,
                "source_url": f"{self.base_url}/patent/{patent_number}",
            }

        except Exception as e:
            logger.error(f"Error parsing patent detail: {e}")
            return None
