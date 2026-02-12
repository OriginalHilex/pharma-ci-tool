import logging
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from database.models import (
    Asset,
    Indication,
    ClinicalTrial,
    Publication,
    NewsArticle,
    Patent,
)
from database.connection import get_session

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and store collected data into the database."""

    def process_clinical_trials(
        self,
        trials: list[dict[str, Any]],
        asset_id: int | None = None,
        indication_id: int | None = None,
    ) -> int:
        """
        Store clinical trial data.

        Args:
            trials: List of trial records from collector
            asset_id: Associated asset ID (if known)
            indication_id: Associated indication ID (if known)

        Returns:
            Number of records upserted
        """
        if not trials:
            return 0

        count = 0
        with get_session() as session:
            for trial in trials:
                try:
                    stmt = insert(ClinicalTrial).values(
                        nct_id=trial["nct_id"],
                        asset_id=asset_id,
                        indication_id=indication_id,
                        title=trial.get("title"),
                        status=trial.get("status"),
                        phase=trial.get("phase"),
                        start_date=trial.get("start_date"),
                        completion_date=trial.get("completion_date"),
                        enrollment=trial.get("enrollment"),
                        sponsor=trial.get("sponsor"),
                        primary_endpoint=trial.get("primary_endpoint"),
                        results_summary=trial.get("summary"),
                        source_url=trial.get("source_url"),
                        raw_data=trial.get("raw_data"),
                    ).on_conflict_do_update(
                        index_elements=["nct_id"],
                        set_={
                            "status": trial.get("status"),
                            "phase": trial.get("phase"),
                            "enrollment": trial.get("enrollment"),
                            "completion_date": trial.get("completion_date"),
                            "primary_endpoint": trial.get("primary_endpoint"),
                            "results_summary": trial.get("summary"),
                            "raw_data": trial.get("raw_data"),
                        },
                    )
                    session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.error(f"Error storing trial {trial.get('nct_id')}: {e}")

        logger.info(f"Processed {count} clinical trials")
        return count

    def process_publications(
        self,
        publications: list[dict[str, Any]],
        asset_id: int | None = None,
    ) -> int:
        """Store publication data."""
        if not publications:
            return 0

        count = 0
        with get_session() as session:
            for pub in publications:
                try:
                    stmt = insert(Publication).values(
                        pmid=pub["pmid"],
                        asset_id=asset_id,
                        title=pub.get("title"),
                        authors=pub.get("authors"),
                        journal=pub.get("journal"),
                        publication_date=pub.get("publication_date"),
                        abstract=pub.get("abstract"),
                        doi=pub.get("doi"),
                        source_url=pub.get("source_url"),
                    ).on_conflict_do_update(
                        index_elements=["pmid"],
                        set_={
                            "title": pub.get("title"),
                            "authors": pub.get("authors"),
                            "abstract": pub.get("abstract"),
                        },
                    )
                    session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.error(f"Error storing publication {pub.get('pmid')}: {e}")

        logger.info(f"Processed {count} publications")
        return count

    def process_news(
        self,
        articles: list[dict[str, Any]],
        asset_id: int | None = None,
    ) -> int:
        """Store news article data."""
        if not articles:
            return 0

        count = 0
        with get_session() as session:
            for article in articles:
                try:
                    stmt = insert(NewsArticle).values(
                        asset_id=asset_id,
                        title=article.get("title"),
                        source=article.get("source"),
                        published_at=article.get("published_at"),
                        url=article.get("url"),
                        summary=article.get("summary"),
                        sentiment_score=article.get("sentiment_score"),
                    ).on_conflict_do_nothing(
                        index_elements=["url"],
                    )
                    result = session.execute(stmt)
                    if result.rowcount > 0:
                        count += 1
                except Exception as e:
                    logger.error(f"Error storing news article: {e}")

        logger.info(f"Processed {count} news articles")
        return count

    def process_patents(
        self,
        patents: list[dict[str, Any]],
        asset_id: int | None = None,
    ) -> int:
        """Store patent data."""
        if not patents:
            return 0

        count = 0
        with get_session() as session:
            for patent in patents:
                try:
                    stmt = insert(Patent).values(
                        patent_number=patent["patent_number"],
                        asset_id=asset_id,
                        title=patent.get("title"),
                        assignee=patent.get("assignee"),
                        filing_date=patent.get("filing_date"),
                        grant_date=patent.get("grant_date"),
                        abstract=patent.get("abstract"),
                        claims_count=patent.get("claims_count"),
                        source_url=patent.get("source_url"),
                    ).on_conflict_do_update(
                        index_elements=["patent_number"],
                        set_={
                            "title": patent.get("title"),
                            "assignee": patent.get("assignee"),
                            "grant_date": patent.get("grant_date"),
                            "abstract": patent.get("abstract"),
                            "claims_count": patent.get("claims_count"),
                        },
                    )
                    session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.error(f"Error storing patent {patent.get('patent_number')}: {e}")

        logger.info(f"Processed {count} patents")
        return count

    def get_assets_with_indications(self, session: Session) -> list[tuple[Asset, list[Indication]]]:
        """Get all assets with their associated indications."""
        assets = session.query(Asset).all()
        result = []
        for asset in assets:
            indications = [ai.indication for ai in asset.indications]
            result.append((asset, indications))
        return result

    def link_trial_to_asset(
        self,
        session: Session,
        nct_id: str,
        asset_id: int,
    ) -> bool:
        """Link an existing trial to an asset."""
        trial = session.query(ClinicalTrial).filter_by(nct_id=nct_id).first()
        if trial:
            trial.asset_id = asset_id
            return True
        return False
