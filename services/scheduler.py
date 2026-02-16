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
from config.search_config import get_search_config

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_collection_job():
    """Run data collection for all tracked assets and indications using search config."""
    logger.info("Starting scheduled data collection...")

    search_config = get_search_config()
    processor = DataProcessor()

    # Resolve DB IDs
    with get_session() as session:
        db_assets = {a.name: a.id for a in session.query(Asset).all()}
        db_indications = {i.name: i.id for i in session.query(Indication).all()}

    # ── Asset-specific monitoring ────────────────────────────────────
    for asset_cfg in search_config.assets:
        logger.info(f"Asset monitoring: {asset_cfg.name}")
        asset_id = db_assets.get(asset_cfg.name)

        # Clinical trials
        with ClinicalTrialsCollector() as collector:
            trials = collector.collect_by_asset(asset_cfg)
            processor.process_clinical_trials(trials, asset_id=asset_id, search_type="asset")

        # Publications
        with PubMedCollector() as collector:
            pubs = collector.collect_by_asset(asset_cfg)
            processor.process_publications(pubs, asset_id=asset_id, search_type="asset")

        # News
        with NewsCollector() as collector:
            news = collector.collect_by_asset(asset_cfg)
            processor.process_news(news, asset_id=asset_id, search_type="asset")

        # Patents
        with PatentsCollector() as collector:
            patents = collector.collect_by_asset(asset_cfg, recent_days=search_config.patent_recent_days)
            processor.process_patents(patents, asset_id=asset_id, search_type="asset")

    # ── Disease discovery monitoring ─────────────────────────────────
    for disease_cfg in search_config.diseases:
        logger.info(f"Disease discovery: {disease_cfg.name}")
        indication_id = db_indications.get(disease_cfg.name)

        # Clinical trials (interventional only)
        with ClinicalTrialsCollector() as collector:
            trials = collector.collect_by_disease(disease_cfg)
            processor.process_clinical_trials(
                trials, indication_id=indication_id, search_type="disease_discovery"
            )

        # PubMed (disease + intervention keywords)
        with PubMedCollector() as collector:
            pubs = collector.collect_by_disease(
                disease_cfg, search_config.intervention_keywords
            )
            processor.process_publications(pubs, search_type="disease_discovery")

        # News (disease + discovery keywords)
        with NewsCollector() as collector:
            news = collector.collect_by_disease(
                disease_cfg, search_config.news_discovery_keywords
            )
            processor.process_news(news, search_type="disease_discovery")

        # Patents (disease)
        with PatentsCollector() as collector:
            patents = collector.collect_by_disease(disease_cfg, recent_days=search_config.patent_recent_days)
            processor.process_patents(patents, search_type="disease_discovery")

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
