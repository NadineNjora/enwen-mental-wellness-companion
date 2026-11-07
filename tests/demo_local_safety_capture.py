r"""Opt-in proof of local Mailpit capture with rollback-only fictional DB records.

Default: no send and no database access. To run deliberately from repo root:
  $env:ENWEN_LOCAL_MAIL_DEMO = 'yes'
  .\backend\.venv\Scripts\python.exe -B tests/demo_local_safety_capture.py
  Remove-Item Env:ENWEN_LOCAL_MAIL_DEMO

This creates ONE fixed synthetic message in existing LOCAL Mailpit. It never
starts Docker, sends live SMS, creates a public account or reads inbox messages.
"""
import os
import sys


if os.getenv("ENWEN_LOCAL_MAIL_DEMO") != "yes":
    print("Skipped: no message sent. Set ENWEN_LOCAL_MAIL_DEMO=yes only to deliberately capture one synthetic message in LOCAL Mailpit.")
    raise SystemExit(0)

# Import the configured DB/transport only after the deliberate opt-in.
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import safety_alerts as alerts
from database import engine
from models import Consent, User
from registration import CONSENT_VERSION, CONTACT_CONSENT_VERSION
from safety_models import SafetyAlert
from trusted_contact_models import TrustedContact
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateIndex, CreateTable

tables = [User.__table__, Consent.__table__, TrustedContact.__table__, SafetyAlert.__table__]
real_local_send = alerts.send_test_email
send_count = 0


def local_capture(**message):
    global send_count
    # Keep this proof constrained to the existing fixed neutral body and local
    # @example.com-only mail helper, even if the surrounding module changes.
    assert message["recipient"] == "confirmed@example.com"
    assert message["subject"] == alerts.TEST_SUBJECT
    assert message["body"] == alerts.TEST_BODY
    send_count += 1
    real_local_send(**message)


failure = None
result = None
with engine.connect() as connection:
    names = set(inspect(connection).get_table_names(schema="public"))
    before = {table.name:connection.scalar(text("SELECT count(*) FROM public." + table.name)) for table in tables if table.name in names}
    connection.rollback()
    outer = connection.begin()
    try:
        connection.execute(text("SET LOCAL statement_timeout = '5s'"))
        for table in tables:
            ddl = str(CreateTable(table).compile(dialect=connection.dialect)).replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1)
            connection.exec_driver_sql(ddl)
            for index in table.indexes: connection.execute(CreateIndex(index))
        connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))

        def isolated_session(bind):
            assert bind is connection and outer.is_active
            return RealSession(bind=connection, join_transaction_mode="create_savepoint")

        user_id, contact_id, request_id = uuid4(), uuid4(), uuid4()
        with isolated_session(connection) as db:
            db.add(User(user_id=user_id, email="local-demo-student@example.com", display_name="Fictional Local Demonstration", password_hash="synthetic-account-cannot-login"))
            db.flush()
            db.add(TrustedContact(contact_id=contact_id, user_id=user_id, full_name="Fictional Local Contact", email="confirmed@example.com",
                confirmation_status="confirmed", confirmed_at=connection.scalar(select(func.clock_timestamp()))))
            db.add_all([
                Consent(user_id=user_id, consent_type="wellness_use", notice_version=CONSENT_VERSION, notice_text="Synthetic local demonstration consent", decision="accepted"),
                Consent(user_id=user_id, consent_type="contact_alert", notice_version=CONTACT_CONSENT_VERSION, notice_text="Synthetic local contact-testing consent", decision="accepted"),
            ])
            db.commit()
        with patch.object(alerts, "engine", connection), patch.object(alerts, "Session", isolated_session), patch.object(alerts, "send_test_email", local_capture):
            result = alerts.create_alert(user_id, request_id, demonstration=True)
            replay = alerts.create_alert(user_id, request_id, demonstration=True)
            assert replay == result, "request replay must return the same recorded event"
            assert send_count == 1, "replay must not attempt a second capture"
            assert connection.scalar(select(func.count()).select_from(SafetyAlert)) == 1
            assert result["alert"]["status"] == "local_test_captured", "local SMTP capture was not confirmed"
    except Exception as error:
        failure = type(error).__name__
    finally:
        outer.rollback()
    after = {name:connection.scalar(text("SELECT count(*) FROM public." + name)) for name in before}
    assert before == after, "public records must remain unchanged"
    assert connection.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")) == 0

if failure:
    print("Local capture proof did not complete. Error type:", failure)
    print("All temporary database records were rolled back. Check Mailpit before retrying; an uncertain capture may already exist.")
    raise SystemExit(1)

print("Confirmed: ONE fixed synthetic support-flow email captured by LOCAL Mailpit.")
print("Confirmed: replay used the same event and made no second send attempt.")
print("Confirmed: all fictional database rows rolled back; existing accounts untouched.")
print("No real person or phone was contacted. No live SMS was sent. No inbox messages were read.")
