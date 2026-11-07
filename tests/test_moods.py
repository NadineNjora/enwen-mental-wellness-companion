"""Current mood API against isolated PostgreSQL TEMP tables, always rolled back."""
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import authentication
import moods
from database import engine
from main import validation_error_handler
from migrate_mood_scale import fingerprint
from models import MoodEntry, User

app = FastAPI()
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(moods.router)
first, second = uuid4(), uuid4()
profiles = [authentication.AccountResponse(
    user_id=first, email="mood-scale-test@example.com", display_name="Fictional Student",
    wellness_consent_current=True,
)]
app.dependency_overrides[authentication.get_current_user] = lambda: profiles[0]
passed = []


def check(name, condition):
    assert condition, name
    passed.append(name)


with engine.connect() as connection:
    public_before = fingerprint(connection)
    connection.rollback()
    transaction = connection.begin()
    try:
        connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))
        for table in (User.__table__, MoodEntry.__table__):
            ddl = str(CreateTable(table).compile(dialect=connection.dialect))
            connection.exec_driver_sql(ddl.replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1))
            assert connection.scalar(text("SELECT relpersistence='t' FROM pg_class WHERE oid=to_regclass(:name)"), {"name": table.name})
        check("foreign key points only to a temporary users table", connection.scalar(text(
            "SELECT bool_and(parent.relpersistence='t') FROM pg_constraint c "
            "JOIN pg_class parent ON parent.oid=c.confrelid "
            "WHERE c.conrelid='pg_temp.mood_entries'::regclass AND c.contype='f'"
        )) is True)
        for user_id in (first, second):
            connection.execute(insert(User).values(user_id=user_id, email=str(user_id)+"@example.com", password_hash="synthetic-unused-hash"))
        connection.execute(insert(MoodEntry).values(user_id=first, mood_score=5, scale_max=5, note="Fictional legacy entry"))

        def session(bind, *args, **kwargs):
            assert bind is connection and transaction.is_active
            return RealSession(bind=connection, join_transaction_mode="create_savepoint")

        with patch.object(moods, "engine", connection), patch.object(moods, "Session", session), TestClient(app) as client:
            for score in range(1, 11):
                response = client.post("/moods", json={"mood_score": score, "scale_max": 10, "note": "Fictional scale test"})
                check(f"score {score}/10 saves with its explicit scale", response.status_code == 201 and response.json()["mood_score"] == score and response.json()["scale_max"] == 10)
                check(f"score {score} response is not cached", response.headers.get("cache-control") == "no-store")
            for payload in (
                {"mood_score": 0, "scale_max": 10}, {"mood_score": 11, "scale_max": 10},
                {"mood_score": 5.5, "scale_max": 10}, {"mood_score": "5", "scale_max": 10},
                {"mood_score": True, "scale_max": 10}, {"mood_score": 5},
                {"mood_score": 5, "scale_max": 5}, {"mood_score": 5, "scale_max": 7},
                {"mood_score": 5, "scale_max": 10, "user_id": str(second)},
            ):
                check(f"invalid or stale payload rejected: {payload}", client.post("/moods", json=payload).status_code == 422)
            history = client.get("/moods").json()
            check("history distinguishes legacy 5/5 from new 5/10", any(row["mood_score"] == 5 and row["scale_max"] == 5 for row in history) and any(row["mood_score"] == 5 and row["scale_max"] == 10 for row in history))
            check("invalid submissions created no rows", len(history) == 11)
            profiles[0] = profiles[0].model_copy(update={"user_id": second})
            check("other account has no access to these moods", client.get("/moods").json() == [])
            profiles[0] = profiles[0].model_copy(update={"wellness_consent_current": False})
            check("consent still required to save", client.post("/moods", json={"mood_score": 10, "scale_max": 10}).status_code == 403)
            check("consent still required to read", client.get("/moods").status_code == 403)
    finally:
        transaction.rollback()
    check("public records unchanged after tests", fingerprint(connection) == public_before)
print({"passed": len(passed), "checks": passed, "scope": "temporary tables rolled back; real records unchanged"})
