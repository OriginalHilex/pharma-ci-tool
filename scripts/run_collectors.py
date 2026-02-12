#!/usr/bin/env python3
"""Manually run data collectors for all tracked assets."""

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
        help="Specific asset name to collect for (default: all)",
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

    processor = DataProcessor()

    with get_session() as session:
        # Get assets to process
        if args.asset:
            assets = session.query(Asset).filter_by(name=args.asset).all()
            if not assets:
                logger.error(f"Asset not found: {args.asset}")
                return
        else:
            assets = session.query(Asset).all()

        indications = session.query(Indication).all()

        if not assets:
            logger.warning("No assets in database. Run seed_data.py first.")
            return

        logger.info(f"Collecting data for {len(assets)} assets and {len(indications)} indications")

        for asset in assets:
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing asset: {asset.name}")
            logger.info(f"{'='*50}")

            # Clinical Trials
            if args.source in ["all", "trials"]:
                logger.info("Collecting clinical trials...")
                with ClinicalTrialsCollector() as collector:
                    trials = collector.collect_by_drug(asset.name, max_results=50)
                    count = processor.process_clinical_trials(trials, asset_id=asset.id)
                    logger.info(f"  Stored {count} trials")

            # PubMed
            if args.source in ["all", "pubmed"]:
                logger.info("Collecting publications...")
                with PubMedCollector() as collector:
                    pubs = collector.collect(asset.name, max_results=30)
                    count = processor.process_publications(pubs, asset_id=asset.id)
                    logger.info(f"  Stored {count} publications")

            # News
            if args.source in ["all", "news"]:
                logger.info("Collecting news...")
                with NewsCollector() as collector:
                    news = collector.collect_for_drug(asset.name, max_results=30)
                    count = processor.process_news(news, asset_id=asset.id)
                    logger.info(f"  Stored {count} news articles")

            # Patents
            if args.source in ["all", "patents"]:
                logger.info("Collecting patents...")
                with PatentsCollector() as collector:
                    patents = collector.collect(
                        asset.name,
                        assignee=asset.company.name if asset.company else None,
                        max_results=20,
                    )
                    count = processor.process_patents(patents, asset_id=asset.id)
                    logger.info(f"  Stored {count} patents")

        # Collect competitive landscape for indications
        if args.source in ["all", "trials"]:
            for indication in indications:
                logger.info(f"\n{'='*50}")
                logger.info(f"Collecting competitive landscape: {indication.name}")
                logger.info(f"{'='*50}")

                with ClinicalTrialsCollector() as collector:
                    trials = collector.collect_by_indication(
                        indication.name,
                        max_results=100,
                    )
                    count = processor.process_clinical_trials(
                        trials,
                        indication_id=indication.id,
                    )
                    logger.info(f"  Stored {count} trials for {indication.name}")

    logger.info("\nCollection complete!")


if __name__ == "__main__":
    main()
