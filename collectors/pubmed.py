from typing import Any
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from .base import BaseCollector
from config import settings
from config.search_config import AssetConfig, DiseaseConfig, IndicationConfig

logger = logging.getLogger(__name__)

# Keywords ANDed with target queries to filter out basic biology/diagnostics
PUBMED_TARGET_KEYWORDS = (
    "drug OR therapy OR antibody OR mAb OR monoclonal OR ADC "
    "OR inhibitor OR clinical OR trial OR phase"
)


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
                - max_results: Maximum number of results (default settings.pubmed_max_results)
                - sort: Entrez sort order ("relevance" or "pub date")
                - date_range: Tuple of (start_date, end_date) in YYYY/MM/DD format

        Returns:
            List of publication records
        """
        max_results = kwargs.get("max_results", settings.pubmed_max_results)
        sort = kwargs.get("sort", "relevance")
        date_range = kwargs.get("date_range")

        # Step 1: Search for PMIDs
        pmids = self._search(query, max_results, date_range, sort=sort)
        if not pmids:
            return []

        # Step 2: Fetch article details
        publications = self._fetch_details(pmids)

        logger.info(f"Collected {len(publications)} publications for query: {query}")
        return publications

    def collect_by_asset(self, asset: AssetConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Asset-specific monitoring (indication-agnostic).

        Builds an OR query from all asset aliases so we capture any
        publication mentioning the drug under any name.
        """
        query = asset.or_query()
        logger.info(f"PubMed asset query: {query}")
        return self.collect(query, **kwargs)

    def collect_by_target(self, asset: AssetConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Target/biomarker monitoring: broad keyword search for protein targets.

        Searches PubMed with target aliases ANDed with drug-context keywords
        to filter out basic biology/diagnostics.
        """
        if not asset.targets:
            return []
        query = f"({asset.target_or_query()}) AND ({PUBMED_TARGET_KEYWORDS})"
        kwargs.setdefault("sort", "pub date")
        logger.info(f"PubMed target query: {query}")
        return self.collect(query, **kwargs)

    def collect_by_indication(
        self,
        asset: AssetConfig,
        indication: IndicationConfig,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Indication-level monitoring: disease search linked to an asset.

        Searches PubMed with indication aliases combined with asset aliases
        to find publications about the drug in a specific disease context.
        """
        query = f"({asset.or_query()}) AND ({indication.or_query()})"
        kwargs.setdefault("sort", "pub date")
        logger.info(f"PubMed indication query: {query}")
        return self.collect(query, **kwargs)

    def collect_by_disease(
        self,
        disease: DiseaseConfig,
        intervention_keywords: list[str],
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Disease + intervention discovery.

        Combines disease aliases with intervention keywords to filter out
        pure biology/basic science and focus on pharma interventions.
        """
        disease_part = disease.or_query()
        kw_terms = []
        for kw in intervention_keywords:
            if " " in kw:
                kw_terms.append(f'"{kw}"')
            else:
                kw_terms.append(kw)
        keywords_part = " OR ".join(kw_terms)

        query = f"({disease_part}) AND ({keywords_part})"
        logger.info(f"PubMed disease+intervention query: {query}")
        return self.collect(query, **kwargs)

    def _search(
        self,
        query: str,
        max_results: int,
        date_range: tuple[str, str] | None = None,
        sort: str = "relevance",
    ) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": sort,
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
        """Fetch article details for a list of PMIDs, batched to avoid URL limits."""
        if not pmids:
            return []

        publications = []
        batch_size = 100

        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            }

            if self.api_key:
                params["api_key"] = self.api_key

            try:
                response = self._make_request(
                    f"{self.base_url}/efetch.fcgi",
                    params=params,
                )
                publications.extend(self._parse_xml_response(response.text))
            except Exception as e:
                logger.error(f"Error fetching PubMed details (batch {i // batch_size + 1}): {e}")

        return publications

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

    # Month name/abbreviation → number
    _MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "june": 6, "july": 7, "august": 8, "september": 9,
        "october": 10, "november": 11, "december": 12,
    }

    def _parse_date_element(self, elem: ET.Element) -> datetime | None:
        """Parse a PubMed date element with Year/Month/Day children.

        Handles numeric months (01-12) and abbreviations (Jan, Feb, ...).
        Always returns a date if a year is present.
        """
        year_elem = elem.find("Year")
        if year_elem is None or not year_elem.text:
            return None

        year = int(year_elem.text)
        month = 1
        day = 1

        month_elem = elem.find("Month")
        if month_elem is not None and month_elem.text:
            m = month_elem.text.strip()
            if m.isdigit():
                month = int(m)
            else:
                month = self._MONTH_MAP.get(m.lower(), 1)

        day_elem = elem.find("Day")
        if day_elem is not None and day_elem.text and day_elem.text.strip().isdigit():
            day = int(day_elem.text.strip())

        try:
            return datetime(year, month, day)
        except ValueError:
            # Bad day (e.g. Feb 30) — fall back to first of month
            return datetime(year, month, 1)

    def _parse_medline_date(self, text: str) -> datetime | None:
        """Parse free-text MedlineDate (e.g. 'Jan-Feb 2023', 'Spring 2019', '2018 Dec-2019 Jan').

        Extracts the first 4-digit year and optional month. Never returns None if a year is present.
        """
        # Extract first 4-digit year
        year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
        if not year_match:
            return None

        year = int(year_match.group(1))
        month = 1

        # Try to find a month name/abbreviation
        for token in re.split(r"[\s\-–/]+", text):
            m = self._MONTH_MAP.get(token.lower().rstrip("."))
            if m:
                month = m
                break

        return datetime(year, month, 1)

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

            # Publication date — try multiple sources in order of precision
            pub_date = None

            # 1) ArticleDate (always numeric YYYY-MM-DD)
            article_date_elem = article_elem.find(".//ArticleDate")
            if article_date_elem is not None:
                pub_date = self._parse_date_element(article_date_elem)

            # 2) PubDate (may use month abbreviations)
            if pub_date is None:
                pub_date_elem = article_elem.find(".//PubDate")
                if pub_date_elem is not None:
                    # Check for MedlineDate free-text first
                    medline_date = pub_date_elem.find("MedlineDate")
                    if medline_date is not None and medline_date.text:
                        pub_date = self._parse_medline_date(medline_date.text)
                    else:
                        pub_date = self._parse_date_element(pub_date_elem)

            # 3) DateCompleted
            if pub_date is None:
                date_completed = medline.find(".//DateCompleted")
                if date_completed is not None:
                    pub_date = self._parse_date_element(date_completed)

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
