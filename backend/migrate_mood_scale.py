"""Add scale metadata without converting any previously recorded mood score.

Run with the backend virtual environment. All DDL is transactional. Run this
before deploying the 1-10 API. Unlabelled legacy writers retain a default of 5;
the new API explicitly writes scale_max=10. Re-running is safe.
"""
from sqlalchemy import text

from database import engine


def upgrade(connection, *, schema="public"):
    if schema not in {"public", "pg_temp"}:
        raise ValueError("Only the application or isolated test schema is allowed.")
    table = f"{schema}.mood_entries"
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(text("SET LOCAL statement_timeout = '30s'"))
    if connection.scalar(text("SELECT to_regclass(:table)"), {"table": table}) is None:
        raise RuntimeError("Create the mood table with init_db.py first.")
    connection.execute(text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    has_scale = connection.scalar(text(
        "SELECT EXISTS (SELECT 1 FROM pg_attribute "
        "WHERE attrelid=to_regclass(:table) AND attname='scale_max' AND NOT attisdropped)"
    ), {"table": table})
    if not has_scale:
        invalid = connection.scalar(text(
            f"SELECT count(*) FROM {table} WHERE mood_score NOT BETWEEN 1 AND 5"
        ))
        if invalid:
            raise RuntimeError("Unexpected legacy scores; no changes were committed.")
        connection.execute(text(
            f"ALTER TABLE {table} ADD COLUMN scale_max INTEGER NOT NULL DEFAULT 5"
        ))

    invalid = connection.scalar(text(
        f"SELECT count(*) FROM {table} WHERE scale_max IS NULL "
        "OR scale_max NOT IN (5, 10) OR mood_score NOT BETWEEN 1 AND scale_max"
    ))
    if invalid:
        raise RuntimeError("Invalid scale metadata; no changes were committed.")
    # Default 5 protects requests from older application processes during rollout.
    connection.execute(text(f"ALTER TABLE {table} ALTER COLUMN scale_max SET DEFAULT 5"))
    connection.execute(text(f"ALTER TABLE {table} ALTER COLUMN scale_max SET NOT NULL"))
    constraints = dict(connection.execute(text(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid=to_regclass(:table) AND contype='c'"
    ), {"table": table}).all())
    if "scale_max" not in constraints.get("ck_mood_entries_score", ""):
        connection.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS ck_mood_entries_score"))
        connection.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_mood_entries_score "
            "CHECK (mood_score BETWEEN 1 AND scale_max)"
        ))
    if "ck_mood_entries_scale" not in constraints:
        connection.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_mood_entries_scale CHECK (scale_max IN (5, 10))"
        ))
    return {"legacy_scale": 5, "new_api_scale": 10}


def fingerprint(connection):
    # Compare existing columns without exposing notes, IDs or account details.
    return connection.execute(text("""
        SELECT count(*), md5(COALESCE(string_agg(
            md5(jsonb_build_array(mood_id, user_id, mood_score, note, created_at)::text),
            '' ORDER BY mood_id), ''))
        FROM public.mood_entries
    """)).one()


if __name__ == "__main__":
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("SET LOCAL statement_timeout = '30s'"))
        connection.execute(text("LOCK TABLE public.mood_entries IN ACCESS EXCLUSIVE MODE"))
        before = fingerprint(connection)
        upgrade(connection)
        after = fingerprint(connection)
        if before != after:
            raise RuntimeError("Existing mood data changed; rolling back migration.")
        scales = connection.execute(text(
            "SELECT scale_max, count(*) FROM public.mood_entries GROUP BY scale_max ORDER BY scale_max"
        )).all()
    print(f"Migration complete. Preserved all {before[0]} existing scores, notes, IDs and timestamps.")
    print("Rows by original scale:", scales)
