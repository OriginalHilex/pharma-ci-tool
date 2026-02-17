import logging
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from database.models import (
    Asset,
    Indication,
    ClinicalTrial,
    ClinicalTrialChange,
    Publication,
    NewsArticle,
    Patent,
)
from database.connection import get_session

logger = logging.getLogger(__name__)

# Fields tracked for change detection on clinical trials
TRACKED_TRIAL_FIELDS = ["status", "phase", "enrollment", "completion_date"]


class DataProcessor:
    """Process and store collected data into the database."""

    def process_clinical_trials(
        self,
        trials: list[dict[str, Any]],
        asset_id: int | None = None,
        indication_id: int | None = None,
        search_type: str | None = None,
    ) -> int:
        """
        Store clinical trial data with change detection.

        Before upserting, compares tracked fields against existing records
        and logs changes to clinical_trial_changes.
        """
        if not trials:
            return 0

        count = 0
        with get_session() as session:
            for trial in trials:
                try:
                    nct_id = trial["nct_id"]

                    # Detect changes against existing record
                    existing = session.query(ClinicalTrial).filter_by(nct_id=nct_id).first()
                    if existing:
                        self._detect_trial_changes(session, existing, trial)

                    stmt = insert(ClinicalTrial).values(
                        nct_id=nct_id,
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
                        last_updated=trial.get("last_updated"),
                        search_type=search_type,
                        raw_data=trial.get("raw_data"),
                    )
                    # Use COALESCE to merge asset_id and indication_id:
                    # new value wins if non-null, otherwise keep existing
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["nct_id"],
                        set_={
                            "asset_id": func.coalesce(
                                stmt.excluded.asset_id, ClinicalTrial.asset_id
                            ),
                            "indication_id": func.coalesce(
                                stmt.excluded.indication_id, ClinicalTrial.indication_id
                            ),
                            "status": trial.get("status"),
                            "phase": trial.get("phase"),
                            "enrollment": trial.get("enrollment"),
                            "completion_date": trial.get("completion_date"),
                            "primary_endpoint": trial.get("primary_endpoint"),
                            "results_summary": trial.get("summary"),
                            "last_updated": trial.get("last_updated"),
                            "raw_data": trial.get("raw_data"),
                        },
                    )
                    session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.error(f"Error storing trial {trial.get('nct_id')}: {e}")

        logger.info(f"Processed {count} clinical trials")
        return count

    def _detect_trial_changes(
        self,
        session: Session,
        existing: ClinicalTrial,
        new_data: dict[str, Any],
    ) -> None:
        """Compare tracked fields and record changes."""
        for field_name in TRACKED_TRIAL_FIELDS:
            old_value = getattr(existing, field_name, None)
            new_value = new_data.get(field_name)

            # Normalize to string for comparison
            old_str = str(old_value) if old_value is not None else None
            new_str = str(new_value) if new_value is not None else None

            if old_str != new_str and new_str is not None:
                change = ClinicalTrialChange(
                    nct_id=existing.nct_id,
                    field_name=field_name,
                    old_value=old_str,
                    new_value=new_str,
                )
                session.add(change)
                logger.info(
                    f"Change detected: {existing.nct_id} {field_name}: "
                    f"{old_str} -> {new_str}"
                )

    def process_publications(
        self,
        publications: list[dict[str, Any]],
        asset_id: int | None = None,
        search_type: str | None = None,
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
                        search_type=search_type,
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
        search_type: str | None = None,
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
                        search_type=search_type,
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
        search_type: str | None = None,
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
                        search_type=search_type,
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
