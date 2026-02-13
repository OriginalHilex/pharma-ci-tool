#!/usr/bin/env python3
"""Manually run data collectors using centralized search configuration."""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run data collectors")
    parser.add_argument(
        "--source",
        choices=["all", "trials", "pubmed", "news", "patents"],
        default="all",
        help="Which data source to collect from",
    )
    parser.add_argument(
        "--asset",
        type=str,
        help="Specific asset name to collect for (default: all from config)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to search_config.yaml (default: config/search_config.yaml)",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=7,
        help="For patents: only fetch patents from the last N days (default: 7)",
    )
    args = parser.parse_args()

    from database.connection import get_session
    from database.models import Asset, Indication
    from collectors import (
        ClinicalTrialsCollector,
        PubMedCollector,
        NewsCollector,
        PatentsCollector,
    )
    from services.data_processor import DataProcessor
    from config.search_config import load_search_config

    search_config = load_search_config(args.config)
    processor = DataProcessor()

    # Filter to specific asset if requested
    asset_configs = search_config.assets
    if args.asset:
        asset_configs = [a for a in asset_configs if args.asset.lower() in a.name.lower()]
        if not asset_configs:
            logger.error(f"Asset not found in config: {args.asset}")
            return

    logger.info(
        f"Collecting data for {len(asset_configs)} assets and "
        f"{len(search_config.diseases)} diseases"
    )

    # Resolve asset DB IDs for linking
    with get_session() as session:
        db_assets = {a.name: a.id for a in session.query(Asset).all()}
        db_indications = {i.name: i.id for i in session.query(Indication).all()}

    # ── Asset-specific monitoring (indication-agnostic) ──────────────
    for asset_cfg in asset_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Asset monitoring: {asset_cfg.name}")
        logger.info(f"  Aliases: {', '.join(asset_cfg.aliases)}")
        logger.info(f"{'='*60}")

        asset_id = db_assets.get(asset_cfg.name)

        # Clinical Trials — asset
        if args.source in ["all", "trials"]:
            logger.info("  [trials] Collecting by asset aliases...")
            with ClinicalTrialsCollector() as collector:
                trials = collector.collect_by_asset(asset_cfg, max_results=50)
                count = processor.process_clinical_trials(
                    trials, asset_id=asset_id, search_type="asset"
                )
                logger.info(f"  [trials] Stored {count} trials")

        # PubMed — asset
        if args.source in ["all", "pubmed"]:
            logger.info("  [pubmed] Collecting by asset aliases...")
            with PubMedCollector() as collector:
                pubs = collector.collect_by_asset(asset_cfg, max_results=30)
                count = processor.process_publications(
                    pubs, asset_id=asset_id, search_type="asset"
                )
                logger.info(f"  [pubmed] Stored {count} publications")

        # News — asset
        if args.source in ["all", "news"]:
            logger.info("  [news] Collecting by asset aliases...")
            with NewsCollector() as collector:
                news = collector.collect_by_asset(asset_cfg, max_results=30)
                count = processor.process_news(
                    news, asset_id=asset_id, search_type="asset"
                )
                logger.info(f"  [news] Stored {count} news articles")

        # Patents — asset (recent only)
        if args.source in ["all", "patents"]:
            logger.info(f"  [patents] Collecting by asset aliases (last {args.recent_days} days)...")
            with PatentsCollector() as collector:
                patents = collector.collect_by_asset(
                    asset_cfg,
                    max_results=20,
                    recent_days=args.recent_days,
                )
                count = processor.process_patents(
                    patents, asset_id=asset_id, search_type="asset"
                )
                logger.info(f"  [patents] Stored {count} patents")

    # ── Disease discovery monitoring ─────────────────────────────────
    for disease_cfg in search_config.diseases:
        logger.info(f"\n{'='*60}")
        logger.info(f"Disease discovery: {disease_cfg.name}")
        logger.info(f"  Aliases: {', '.join(disease_cfg.aliases)}")
        logger.info(f"{'='*60}")

        indication_id = db_indications.get(disease_cfg.name)

        # Clinical Trials — disease (interventional only)
        if args.source in ["all", "trials"]:
            logger.info("  [trials] Collecting interventional trials for disease...")
            with ClinicalTrialsCollector() as collector:
                trials = collector.collect_by_disease(disease_cfg, max_results=100)
                count = processor.process_clinical_trials(
                    trials, indication_id=indication_id, search_type="disease_discovery"
                )
                logger.info(f"  [trials] Stored {count} trials")

        # PubMed — disease + intervention keywords
        if args.source in ["all", "pubmed"]:
            logger.info("  [pubmed] Collecting disease + intervention publications...")
            with PubMedCollector() as collector:
                pubs = collector.collect_by_disease(
                    disease_cfg,
                    search_config.intervention_keywords,
                    max_results=30,
                )
                count = processor.process_publications(
                    pubs, search_type="disease_discovery"
                )
                logger.info(f"  [pubmed] Stored {count} publications")

        # News — disease + discovery keywords
        if args.source in ["all", "news"]:
            logger.info("  [news] Collecting disease discovery news...")
            with NewsCollector() as collector:
                news = collector.collect_by_disease(
                    disease_cfg,
                    search_config.news_discovery_keywords,
                    max_results=30,
                )
                count = processor.process_news(
                    news, search_type="disease_discovery"
                )
                logger.info(f"  [news] Stored {count} news articles")

        # Patents — disease (recent only)
        if args.source in ["all", "patents"]:
            logger.info(f"  [patents] Collecting disease-linked patents (last {args.recent_days} days)...")
            with PatentsCollector() as collector:
                patents = collector.collect_by_disease(
                    disease_cfg,
                    max_results=20,
                    recent_days=args.recent_days,
                )
                count = processor.process_patents(
                    patents, search_type="disease_discovery"
                )
                logger.info(f"  [patents] Stored {count} patents")

    logger.info("\nCollection complete!")


if __name__ == "__main__":
    main()
