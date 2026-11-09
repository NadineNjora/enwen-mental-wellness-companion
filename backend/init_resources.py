"""Create only the new resource tables and insert missing catalog items.

Existing student records and existing resource rows are never overwritten.
Run from backend with the project's virtual environment.
"""
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from database import engine
from resource_models import ResourceBookmark, WellnessResource
from migrate_resource_admin import ensure_resource_schema
from resource_policy import source


def catalog():
    rows = json.loads(Path(__file__).with_name("resources_catalog.json").read_text(encoding="utf-8"))
    ids = set()
    for row in rows:
        _,publisher=source(row['url'])
        if row['publisher']!=publisher:
            raise ValueError("Catalog must use reviewed publisher URLs.")
        if row["resource_id"] in ids:
            raise ValueError("Duplicate catalog resource ID.")
        ids.add(row["resource_id"])
        row["source_checked_on"] = date.fromisoformat(row["source_checked_on"])
    return rows


def create_resources():
    ensure_resource_schema()
    rows = catalog()
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("SET LOCAL statement_timeout = '30s'"))
        WellnessResource.__table__.create(connection, checkfirst=True)
        ResourceBookmark.__table__.create(connection, checkfirst=True)
        added = connection.execute(insert(WellnessResource).values(rows).on_conflict_do_nothing(index_elements=["resource_id"]).returning(WellnessResource.resource_id)).all()
    print(f"Resource library ready. Added {len(added)} missing resources; existing records preserved.")


if __name__ == "__main__":
    create_resources()
