from typing import Any
import logging
import xml.etree.ElementTree as ET
from .base import BaseCollector
from config import settings

logger = logging.getLogger(__name__)


class PubMedCollector(BaseCollector):
    """Collector for PubMed via NCBI Entrez E-utilities."""

    def __init__(self):
        super().__init__()
        self.base_url = settings.pubmed_api_url
        self.api_key = settings.ncbi_api_key

    def get_source_name(self) -> str:
        return "PubMed"

    def collect(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """
        Collect publications matching the query.

        Args:
            query: Search term (drug name, indication, etc.)
            **kwargs:
                - max_results: Maximum number of results (default 50)
                - date_range: Tuple of (start_date, end_date) in YYYY/MM/DD format

        Returns:
            List of publication records
        """
        max_results = kwargs.get("max_results", 50)
        date_range = kwargs.get("date_range")

        # Step 1: Search for PMIDs
        pmids = self._search(query, max_results, date_range)
        if not pmids:
            return []

        # Step 2: Fetch article details
        publications = self._fetch_details(pmids)

        logger.info(f"Collected {len(publications)} publications for query: {query}")
        return publications

    def _search(
        self,
        query: str,
        max_results: int,
        date_range: tuple[str, str] | None = None,
    ) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }

        if self.api_key:
            params["api_key"] = self.api_key

        if date_range:
            params["datetype"] = "pdat"
            params["mindate"] = date_range[0]
            params["maxdate"] = date_range[1]

        try:
            response = self._make_request(
                f"{self.base_url}/esearch.fcgi",
                params=params,
            )
            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            return []

    def _fetch_details(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Fetch article details for a list of PMIDs."""
        if not pmids:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }

        if self.api_key:
            params["api_key"] = self.api_key

        try:
            response = self._make_request(
                f"{self.base_url}/efetch.fcgi",
                params=params,
            )
            return self._parse_xml_response(response.text)
        except Exception as e:
            logger.error(f"Error fetching PubMed details: {e}")
            return []

    def _parse_xml_response(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse PubMed XML response."""
        publications = []

        try:
            root = ET.fromstring(xml_text)

            for article in root.findall(".//PubmedArticle"):
                pub = self._parse_article(article)
                if pub:
                    publications.append(pub)

        except ET.ParseError as e:
            logger.error(f"Error parsing PubMed XML: {e}")

        return publications

    def _parse_article(self, article: ET.Element) -> dict[str, Any] | None:
        """Parse a single PubMed article."""
        try:
            medline = article.find(".//MedlineCitation")
            if medline is None:
                return None

            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None
            if not pmid:
                return None

            article_elem = medline.find(".//Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_parts = article_elem.findall(".//AbstractText")
            abstract = " ".join(
                (part.text or "") for part in abstract_parts
            )

            # Authors
            authors = []
            for author in article_elem.findall(".//Author"):
                last_name = author.find("LastName")
                fore_name = author.find("ForeName")
                if last_name is not None and last_name.text:
                    name = last_name.text
                    if fore_name is not None and fore_name.text:
                        name = f"{fore_name.text} {last_name.text}"
                    authors.append(name)

            # Journal
            journal_elem = article_elem.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else None

            # Publication date
            pub_date = None
            pub_date_elem = article_elem.find(".//PubDate")
            if pub_date_elem is not None:
                year = pub_date_elem.find("Year")
                month = pub_date_elem.find("Month")
                day = pub_date_elem.find("Day")
                if year is not None and year.text:
                    date_str = year.text
                    if month is not None and month.text:
                        date_str += f"-{month.text}"
                    if day is not None and day.text:
                        date_str += f"-{day.text}"
                    pub_date = self._parse_date(date_str)

            # DOI
            doi = None
            for id_elem in article.findall(".//ArticleId"):
                if id_elem.get("IdType") == "doi":
                    doi = id_elem.text
                    break

            return {
                "pmid": pmid,
                "title": title,
                "authors": "; ".join(authors),
                "journal": journal,
                "publication_date": pub_date,
                "abstract": abstract,
                "doi": doi,
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }

        except Exception as e:
            logger.error(f"Error parsing article: {e}")
            return None
