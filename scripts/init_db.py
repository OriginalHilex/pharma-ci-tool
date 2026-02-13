#!/usr/bin/env python3
"""Initialize the database tables."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect
from database.connection import init_db, get_engine
from database.models import Base


def main():
    print("Initializing database...")

    # Create all tables
    init_db()

    # Verify tables were created
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"\nCreated {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  - {table}")

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    main()
