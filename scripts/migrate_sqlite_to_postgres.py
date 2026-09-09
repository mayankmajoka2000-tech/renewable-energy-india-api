"""
One-time migration: copy every row from the bundled SQLite database into a
Postgres database, preserving primary keys (so foreign-key-style references
by id, and any bookmarked API responses, stay consistent).

Usage:
    export DATABASE_URL=postgresql://renewable:renewable@localhost:5432/renewable_energy_india
    python3 -m scripts.migrate_sqlite_to_postgres

Safe to re-run: each table is copied only if the target table is currently
empty, so accidentally running it twice against an already-migrated Postgres
instance is a no-op (skip + report) rather than a duplicate-row mess.

This does NOT touch the source SQLite file — it only reads from it.
"""
import os
import sys

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.database import DEFAULT_SQLITE_URL
from app.models import Base

CHUNK_SIZE = 5000


def run():
    target_url = os.environ.get("DATABASE_URL")
    if not target_url or target_url.startswith("sqlite"):
        print(
            "DATABASE_URL must be set to a postgresql:// URL for this script "
            "(it's the migration TARGET, not read from app.database's default). "
            "Example:\n"
            "  export DATABASE_URL=postgresql://renewable:renewable@localhost:5432/renewable_energy_india\n"
            "  python3 -m scripts.migrate_sqlite_to_postgres"
        )
        sys.exit(1)

    source_engine = create_engine(DEFAULT_SQLITE_URL)
    target_engine = create_engine(target_url)

    print(f"Source (read-only): {DEFAULT_SQLITE_URL}")
    print(f"Target: {target_url}")

    # Create all tables on the target if they don't exist yet.
    Base.metadata.create_all(bind=target_engine)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)
    src = SourceSession()
    tgt = TargetSession()

    total_copied = 0
    try:
        for table in Base.metadata.sorted_tables:
            target_count = tgt.execute(select(func.count()).select_from(table)).scalar()
            if target_count:
                print(f"  {table.name}: target already has {target_count} rows, skipping")
                continue

            source_count = src.execute(select(func.count()).select_from(table)).scalar()
            if not source_count:
                print(f"  {table.name}: source is empty, nothing to copy")
                continue

            copied = 0
            result = src.execute(select(table))
            while True:
                rows = result.fetchmany(CHUNK_SIZE)
                if not rows:
                    break
                tgt.execute(table.insert(), [dict(row._mapping) for row in rows])
                copied += len(rows)
                print(f"  {table.name}: {copied}/{source_count}", end="\r")
            tgt.commit()

            # Postgres SERIAL/IDENTITY columns need their sequence advanced
            # past the max id we just inserted explicitly, or the next
            # auto-generated insert will collide.
            if target_engine.dialect.name == "postgresql" and "id" in table.c:
                tgt.execute(
                    select(
                        func.setval(
                            func.pg_get_serial_sequence(table.name, "id"),
                            select(func.max(table.c.id)).select_from(table).scalar_subquery(),
                        )
                    )
                )
                tgt.commit()

            print(f"  {table.name}: {copied}/{source_count} copied")
            total_copied += copied
    finally:
        src.close()
        tgt.close()

    print(f"\nMigration complete: {total_copied} rows copied across "
          f"{len(Base.metadata.sorted_tables)} tables.")


if __name__ == "__main__":
    run()
