"""Real PostgreSQL TEMP-table migration checks; no public-table writes."""
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from database import engine
from migrate_mood_scale import upgrade

passed = []
with engine.connect() as connection:
    transaction = connection.begin()
    try:
        connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))
        connection.execute(text("""
            CREATE TEMPORARY TABLE mood_entries (
              mood_id INTEGER PRIMARY KEY, mood_score INTEGER NOT NULL,
              note TEXT, created_at TIMESTAMPTZ DEFAULT now(),
              CONSTRAINT ck_mood_entries_score CHECK(mood_score BETWEEN 1 AND 5)
            )
        """))
        for score in range(1, 6):
            connection.execute(text("INSERT INTO pg_temp.mood_entries (mood_id,mood_score,note) VALUES (:s,:s,'Fictional legacy note')"), {"s": score})
        before = connection.execute(text("SELECT mood_id,mood_score,note,created_at FROM pg_temp.mood_entries ORDER BY mood_id")).all()
        upgrade(connection, schema="pg_temp")
        assert before == connection.execute(text("SELECT mood_id,mood_score,note,created_at FROM pg_temp.mood_entries ORDER BY mood_id")).all()
        assert connection.scalar(text("SELECT count(*) FROM pg_temp.mood_entries WHERE scale_max=5")) == 5
        passed.append("legacy values, notes and timestamps preserved with explicit scale 5")
        upgrade(connection, schema="pg_temp")
        assert connection.scalar(text("SELECT count(*) FROM pg_temp.mood_entries")) == 5
        passed.append("repeat migration is idempotent")
        for score in (1, 10):
            connection.execute(text("INSERT INTO pg_temp.mood_entries (mood_id,mood_score,scale_max) VALUES (:id,:score,10)"), {"id": 10 + score, "score": score})
        passed.append("new 1 and 10 scores accepted on scale 10")
        for index, (score, scale) in enumerate(((0, 10), (11, 10), (6, 5), (5, 7), (1, None))):
            savepoint = connection.begin_nested()
            try:
                connection.execute(text("INSERT INTO pg_temp.mood_entries (mood_id,mood_score,scale_max) VALUES (:id,:score,:scale)"), {"id": 100 + index, "score": score, "scale": scale})
            except IntegrityError:
                savepoint.rollback()
                passed.append(f"database rejects score {score}, scale {scale}")
            else:
                savepoint.rollback()
                raise AssertionError("Invalid score/scale was accepted")
        connection.execute(text("INSERT INTO pg_temp.mood_entries (mood_id,mood_score) VALUES (30,4)"))
        assert connection.scalar(text("SELECT scale_max FROM pg_temp.mood_entries WHERE mood_id=30")) == 5
        passed.append("older writers still label their scores as out of 5")
        assert connection.scalar(text("SELECT relpersistence='t' FROM pg_class WHERE oid='pg_temp.mood_entries'::regclass"))
    finally:
        transaction.rollback()
print({"passed": len(passed), "checks": passed, "scope": "temporary table rolled back; public records untouched"})
