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

        - New NCT IDs: insert + create "new_trial" change record.
        - Existing, same last_updated: skip (only merge asset_id/indication_id if needed).
        - Existing, different last_updated: run field diff, update only if changed.
        """
        if not trials:
            return 0

        new_count = 0
        updated_count = 0
        skipped_count = 0
        with get_session() as session:
            for trial in trials:
                try:
                    nct_id = trial["nct_id"]
                    incoming_last_updated = trial.get("last_updated")

                    existing = session.query(ClinicalTrial).filter_by(nct_id=nct_id).first()

                    if not existing:
                        # ── New trial: insert ────────────────────────
                        new_trial = ClinicalTrial(
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
                            last_updated=incoming_last_updated,
                            search_type=search_type,
                            raw_data=trial.get("raw_data"),
                        )
                        session.add(new_trial)
                        session.flush()
                        session.add(ClinicalTrialChange(
                            nct_id=nct_id,
                            field_name="new_trial",
                            old_value=None,
                            new_value=nct_id,
                        ))
                        new_count += 1
                        continue

                    # ── Existing trial ───────────────────────────
                    # Merge asset_id/indication_id if missing
                    id_merged = False
                    if asset_id and not existing.asset_id:
                        existing.asset_id = asset_id
                        id_merged = True
                    if indication_id and not existing.indication_id:
                        existing.indication_id = indication_id
                        id_merged = True

                    # Normalize to date for comparison (DB stores date, collector parses datetime)
                    existing_lu = existing.last_updated
                    incoming_lu = incoming_last_updated
                    if hasattr(existing_lu, "date"):
                        existing_lu = existing_lu.date()
                    if hasattr(incoming_lu, "date"):
                        incoming_lu = incoming_lu.date()

                    if existing_lu == incoming_lu:
                        # No update needed — count as updated only if IDs were merged
                        if id_merged:
                            updated_count += 1
                        else:
                            skipped_count += 1
                        continue

                    # last_updated differs — run field-level diff
                    has_changes = self._detect_trial_changes(session, existing, trial)

                    if has_changes:
                        existing.title = trial.get("title") or existing.title
                        existing.status = trial.get("status")
                        existing.phase = trial.get("phase")
                        existing.start_date = trial.get("start_date") or existing.start_date
                        existing.completion_date = trial.get("completion_date")
                        existing.enrollment = trial.get("enrollment")
                        existing.sponsor = trial.get("sponsor") or existing.sponsor
                        existing.primary_endpoint = trial.get("primary_endpoint")
                        existing.results_summary = trial.get("summary")
                        existing.raw_data = trial.get("raw_data")
                        updated_count += 1

                    # Always update last_updated when it changed
                    existing.last_updated = incoming_last_updated

                except Exception as e:
                    logger.error(f"Error storing trial {trial.get('nct_id')}: {e}")

        total = new_count + updated_count
        logger.info(
            f"Processed {total} clinical trials "
            f"({new_count} new, {updated_count} updated, {skipped_count} skipped)"
        )
        return total

    def _detect_trial_changes(
        self,
        session: Session,
        existing: ClinicalTrial,
        new_data: dict[str, Any],
    ) -> bool:
        """Compare tracked fields and record changes. Returns True if any changed."""
        found = False
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
                found = True
        return found

    def process_publications(
        self,
        publications: list[dict[str, Any]],
        asset_id: int | None = None,
        indication_id: int | None = None,
        search_type: str | None = None,
    ) -> int:
        """
        Store publication data. Publications are immutable once inserted.

        - New PMID: insert.
        - Existing PMID: merge asset_id/indication_id if missing, nothing else.
        """
        if not publications:
            return 0

        new_count = 0
        with get_session() as session:
            for pub in publications:
                try:
                    pmid = pub["pmid"]
                    existing = session.query(Publication).filter_by(pmid=pmid).first()

                    if not existing:
                        session.add(Publication(
                            pmid=pmid,
                            asset_id=asset_id,
                            indication_id=indication_id,
                            title=pub.get("title") or "(No title)",
                            authors=pub.get("authors"),
                            journal=pub.get("journal"),
                            publication_date=pub.get("publication_date"),
                            abstract=pub.get("abstract"),
                            doi=pub.get("doi"),
                            source_url=pub.get("source_url"),
                            search_type=search_type,
                        ))
                        new_count += 1
                        continue

                    # Merge IDs if missing
                    if asset_id and not existing.asset_id:
                        existing.asset_id = asset_id
                    if indication_id and not existing.indication_id:
                        existing.indication_id = indication_id

                except Exception as e:
                    logger.error(f"Error storing publication {pub.get('pmid')}: {e}")

        logger.info(f"Processed {new_count} new publications (of {len(publications)} incoming)")
        return new_count

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
