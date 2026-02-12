#!/usr/bin/env python3
"""Seed the database with initial data for Zolbetuximab and Gilteritinib."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_session
from database.models import Company, Asset, Indication, AssetIndication


def seed_companies():
    """Seed pharmaceutical companies."""
    companies = [
        {
            "name": "Astellas Pharma",
            "ticker": "4503.T",
            "description": "Astellas Pharma Inc. is a Japanese multinational pharmaceutical company, focused on oncology, immunology, and infectious diseases.",
            "website": "https://www.astellas.com",
        },
    ]
    return companies


def seed_assets():
    """Seed drug assets."""
    assets = [
        {
            "company_name": "Astellas Pharma",
            "name": "Zolbetuximab (Vyloy)",
            "generic_name": "Zolbetuximab",
            "mechanism_of_action": "Anti-CLDN18.2 (Claudin 18.2) monoclonal antibody. CLDN18.2 is a tight junction protein highly expressed in gastric cancer cells. Zolbetuximab binds to CLDN18.2 and induces antibody-dependent cellular cytotoxicity (ADCC) and complement-dependent cytotoxicity (CDC).",
            "stage": "Approved (2024)",
        },
        {
            "company_name": "Astellas Pharma",
            "name": "Gilteritinib (Xospata)",
            "generic_name": "Gilteritinib",
            "mechanism_of_action": "FLT3 (FMS-like tyrosine kinase 3) inhibitor. Targets FLT3-ITD and FLT3-TKD mutations which are common in acute myeloid leukemia (AML). Inhibits FLT3 receptor signaling and induces apoptosis in leukemic cells.",
            "stage": "Approved (2018)",
        },
    ]
    return assets


def seed_indications():
    """Seed medical indications."""
    indications = [
        {
            "name": "Gastric Cancer",
            "therapeutic_area": "Oncology",
            "icd_code": "C16",
        },
        {
            "name": "Gastroesophageal Junction Adenocarcinoma",
            "therapeutic_area": "Oncology",
            "icd_code": "C16.0",
        },
        {
            "name": "Acute Myeloid Leukemia",
            "therapeutic_area": "Oncology/Hematology",
            "icd_code": "C92.0",
        },
    ]
    return indications


def seed_asset_indications():
    """Seed asset-indication relationships."""
    relationships = [
        {
            "asset_name": "Zolbetuximab (Vyloy)",
            "indication_name": "Gastric Cancer",
            "status": "Approved",
            "notes": "FDA approved January 2024 (Vyloy) for HER2-negative, CLDN18.2-positive gastric or GEJ adenocarcinoma in combination with chemotherapy.",
        },
        {
            "asset_name": "Zolbetuximab (Vyloy)",
            "indication_name": "Gastroesophageal Junction Adenocarcinoma",
            "status": "Approved",
            "notes": "Included in gastric cancer approval. Used in combination with fluoropyrimidine and platinum-containing chemotherapy.",
        },
        {
            "asset_name": "Gilteritinib (Xospata)",
            "indication_name": "Acute Myeloid Leukemia",
            "status": "Approved",
            "notes": "FDA approved November 2018 (Xospata) for relapsed or refractory AML with FLT3 mutation.",
        },
    ]
    return relationships


def main():
    print("Seeding database with initial data...")

    with get_session() as session:
        # Seed companies
        print("\nSeeding companies...")
        for company_data in seed_companies():
            existing = session.query(Company).filter_by(name=company_data["name"]).first()
            if not existing:
                company = Company(**company_data)
                session.add(company)
                print(f"  Added: {company_data['name']}")
            else:
                print(f"  Exists: {company_data['name']}")

        session.flush()

        # Seed assets
        print("\nSeeding assets...")
        for asset_data in seed_assets():
            company_name = asset_data.pop("company_name")
            company = session.query(Company).filter_by(name=company_name).first()

            existing = session.query(Asset).filter_by(
                name=asset_data["name"],
                company_id=company.id
            ).first()

            if not existing:
                asset = Asset(company_id=company.id, **asset_data)
                session.add(asset)
                print(f"  Added: {asset_data['name']} ({company_name})")
            else:
                print(f"  Exists: {asset_data['name']}")

        session.flush()

        # Seed indications
        print("\nSeeding indications...")
        for indication_data in seed_indications():
            existing = session.query(Indication).filter_by(name=indication_data["name"]).first()
            if not existing:
                indication = Indication(**indication_data)
                session.add(indication)
                print(f"  Added: {indication_data['name']}")
            else:
                print(f"  Exists: {indication_data['name']}")

        session.flush()

        # Seed asset-indication relationships
        print("\nSeeding asset-indication relationships...")
        for rel_data in seed_asset_indications():
            asset = session.query(Asset).filter_by(name=rel_data["asset_name"]).first()
            indication = session.query(Indication).filter_by(name=rel_data["indication_name"]).first()

            if asset and indication:
                existing = session.query(AssetIndication).filter_by(
                    asset_id=asset.id,
                    indication_id=indication.id
                ).first()

                if not existing:
                    ai = AssetIndication(
                        asset_id=asset.id,
                        indication_id=indication.id,
                        status=rel_data["status"],
                        notes=rel_data["notes"],
                    )
                    session.add(ai)
                    print(f"  Added: {rel_data['asset_name']} - {rel_data['indication_name']}")
                else:
                    print(f"  Exists: {rel_data['asset_name']} - {rel_data['indication_name']}")

    print("\nSeeding complete!")
    print("\nSummary:")
    print("  - Company: Astellas Pharma")
    print("  - Assets: Zolbetuximab (Vyloy), Gilteritinib (Xospata)")
    print("  - Indications: Gastric Cancer, GEJ Adenocarcinoma, AML")


if __name__ == "__main__":
    main()
