import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from collectors import (
    ClinicalTrialsCollector,
    PubMedCollector,
    NewsCollector,
    PatentsCollector,
)
from services.data_processor import DataProcessor
from database.connection import get_session
from database.models import Asset, Indication
from config import settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_collection_job():
    """Run data collection for all tracked assets and indications."""
    logger.info("Starting scheduled data collection...")

    processor = DataProcessor()

    with get_session() as session:
        # Get all assets and their indications
        assets = session.query(Asset).all()
        indications = session.query(Indication).all()

        # Collect data for each asset
        for asset in assets:
            logger.info(f"Collecting data for asset: {asset.name}")

            # Clinical trials for the drug
            with ClinicalTrialsCollector() as collector:
                trials = collector.collect_by_drug(asset.name)
                processor.process_clinical_trials(trials, asset_id=asset.id)

            # Publications
            with PubMedCollector() as collector:
                pubs = collector.collect(asset.name)
                processor.process_publications(pubs, asset_id=asset.id)

            # News
            with NewsCollector() as collector:
                news = collector.collect_for_drug(asset.name)
                processor.process_news(news, asset_id=asset.id)

            # Patents
            with PatentsCollector() as collector:
                patents = collector.collect(
                    asset.name,
                    assignee=asset.company.name if asset.company else None,
                )
                processor.process_patents(patents, asset_id=asset.id)

        # Collect competitive landscape for each indication
        for indication in indications:
            logger.info(f"Collecting competitive landscape for: {indication.name}")

            with ClinicalTrialsCollector() as collector:
                trials = collector.collect_by_indication(indication.name)
                processor.process_clinical_trials(trials, indication_id=indication.id)

    logger.info("Scheduled data collection completed.")


def start_scheduler():
    """Start the background scheduler for periodic data collection."""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    _scheduler = BackgroundScheduler()

    # Add the collection job
    _scheduler.add_job(
        run_collection_job,
        trigger=IntervalTrigger(hours=settings.collection_interval_hours),
        id="data_collection",
        name="Collect data from all sources",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started. Collection interval: {settings.collection_interval_hours} hours"
    )


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler

    if _scheduler is None:
        logger.warning("Scheduler not running")
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Scheduler stopped")


def trigger_collection_now():
    """Manually trigger a collection run immediately."""
    logger.info("Manually triggering data collection...")
    run_collection_job()
