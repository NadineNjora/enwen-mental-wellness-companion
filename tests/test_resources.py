"""Resource routes with real PostgreSQL TEMP tables; public records preserved."""
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import insert, text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import authentication
import resources
from database import engine
from init_resources import catalog
from main import validation_error_handler
from models import User
from resource_models import WellnessResource, ResourceBookmark

app = FastAPI()
app.include_router(resources.router)
app.add_exception_handler(RequestValidationError, validation_error_handler)
first, second = uuid4(), uuid4()
profile = authentication.AccountResponse(user_id=first, email="resource-test@example.com", display_name="Fictional Student", wellness_consent_current=True)
current = [profile]
passed = []


def check(label, condition):
    assert condition, label
    passed.append(label)


def counts(connection):
    return {name: connection.scalar(text("SELECT count(*) FROM public." + name)) for name in ("users", "mood_entries", "journal_entries", "wellness_resources", "resource_bookmarks")}


with engine.connect() as connection:
    before = counts(connection)
    connection.rollback()
    outer = connection.begin()
    try:
        connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))
        for table in (User.__table__, WellnessResource.__table__, ResourceBookmark.__table__):
            ddl = str(CreateTable(table).compile(dialect=connection.dialect))
            connection.exec_driver_sql(ddl.replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1))
            assert connection.scalar(text("SELECT relpersistence='t' FROM pg_class WHERE oid=to_regclass(:name)"), {"name": table.name})
        for uid in (first, second):
            connection.execute(insert(User).values(user_id=uid, email=str(uid)+"@example.com", password_hash="synthetic-unused-hash"))
        connection.execute(insert(WellnessResource), catalog())

        def session(bind, *args, **kwargs):
            assert bind is connection and outer.is_active
            return RealSession(bind=connection, join_transaction_mode="create_savepoint")

        with patch.object(resources, "engine", connection), patch.object(resources, "Session", session), TestClient(app) as client:
            check("anonymous access denied", client.get("/resources").status_code == 401)
            app.dependency_overrides[authentication.get_current_user] = lambda: current[0]
            result = client.get("/resources")
            check("complete expanded catalog returned", result.status_code == 200 and len(result.json()) == len(catalog()))
            check("resource responses are not cached", result.headers.get("cache-control") == "no-store")
            check("every source is an HTTPS publisher link", all(row["url"].startswith("https://") for row in result.json()))
            check("no saved items initially", not any(row["saved"] for row in result.json()))
            check("category filter matches one topic", [row["resource_id"] for row in client.get("/resources?category=rest").json()] == ["nhs-sleep"])
            check("case-insensitive search", len(client.get("/resources?q=wOrLd%20HeAlTh").json()) == 1)
            check("wildcard search is literal", client.get("/resources", params={"q": "%"}).json() == [])
            check("unknown category rejected", client.get("/resources?category=unknown").status_code == 422)
            check("overlong query rejected", client.get("/resources", params={"q": "x"*101}).status_code == 422)
            check("saved filter initially empty", client.get("/resources?saved_only=true").json() == [])
            save = client.put("/resources/who-stress-guide/bookmark")
            check("saving returns empty 204", save.status_code == 204 and not save.content and save.headers.get("cache-control") == "no-store")
            check("repeated save is idempotent", client.put("/resources/who-stress-guide/bookmark").status_code == 204 and connection.scalar(text("SELECT count(*) FROM pg_temp.resource_bookmarks")) == 1)
            saved = client.get("/resources?saved_only=true").json()
            check("saved reading round-trips through the database", len(saved) == 1 and saved[0]["resource_id"] == "who-stress-guide" and saved[0]["saved"])
            current[0] = profile.model_copy(update={"user_id": second})
            check("another account cannot see the bookmark", client.get("/resources?saved_only=true").json() == [])
            check("another account's unsave cannot remove it", client.delete("/resources/who-stress-guide/bookmark").status_code == 204 and connection.scalar(text("SELECT count(*) FROM pg_temp.resource_bookmarks")) == 1)
            check("another account can save its own copy", client.put("/resources/who-stress-guide/bookmark").status_code == 204 and connection.scalar(text("SELECT count(*) FROM pg_temp.resource_bookmarks")) == 2)
            check("unknown resource cannot be bookmarked", client.put("/resources/unknown/bookmark").status_code == 404)
            current[0] = profile.model_copy(update={"wellness_consent_current": False})
            check("consent required to read", client.get("/resources").status_code == 403)
            check("consent required to save", client.put("/resources/nhs-sleep/bookmark").status_code == 403)
            check("owner can remove an old bookmark without current consent", client.delete("/resources/who-stress-guide/bookmark").status_code == 204)
            current[0] = profile
            check("unsaved item no longer appears in saved list", client.get("/resources?saved_only=true").json() == [])
            check("removing a bookmark preserves catalog", len(client.get("/resources").json()) == len(catalog()))
            check("other user's bookmark preserved", connection.scalar(text("SELECT count(*) FROM pg_temp.resource_bookmarks")) == 1)
    finally:
        outer.rollback()
    check("public user data and catalog counts unchanged by tests", counts(connection) == before)
print({"passed": len(passed), "checks": passed, "scope": "TEMP tables rolled back; public records untouched"})
