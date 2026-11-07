"""Local support-outbox tests: PostgreSQL TEMP tables and fake SMTP only."""
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import safety_alerts as alerts
from safety_models import SafetyAlert
from database import engine
from models import User, Consent
from registration import CONSENT_VERSION, CONTACT_CONSENT_VERSION
from trusted_contact_models import TrustedContact
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable, CreateIndex
from fastapi import HTTPException

checks, captured = [], []
def check(name, condition):
    assert condition, name
    checks.append(name)


tables = [User.__table__, Consent.__table__, TrustedContact.__table__, SafetyAlert.__table__]
with engine.connect() as connection:
    existing = set(inspect(connection).get_table_names(schema="public"))
    before = {table.name:connection.scalar(text("SELECT count(*) FROM public." + table.name)) for table in tables if table.name in existing}
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

        def account(label, *, contact_status=None, email=None, consent=True):
            uid, cid = uuid4(), None
            with isolated_session(connection) as db:
                db.add(User(user_id=uid, email=label + "@example.com", display_name="Synthetic private display name", password_hash="synthetic-no-login"))
                db.flush()
                if contact_status is not None:
                    cid = uuid4()
                    db.add(TrustedContact(contact_id=cid, user_id=uid, full_name="Synthetic trusted name", email=email or label + ".contact@example.com",
                        confirmation_status=contact_status, confirmed_at=connection.scalar(select(func.clock_timestamp())) if contact_status == "confirmed" else None))
                if consent:
                    db.add_all([
                        Consent(user_id=uid, consent_type="wellness_use", notice_version=CONSENT_VERSION, notice_text="Synthetic wellbeing consent", decision="accepted"),
                        Consent(user_id=uid, consent_type="contact_alert", notice_version=CONTACT_CONSENT_VERSION, notice_text="Synthetic local testing consent", decision="accepted"),
                    ])
                db.commit()
            return uid, cid

        def capture(**email):
            captured.append(email)
            claim = connection.scalar(select(SafetyAlert.status).order_by(SafetyAlert.created_at.desc()).limit(1))
            check("dispatch claim exists before SMTP", claim == "dispatching")

        with patch.object(alerts, "engine", connection), patch.object(alerts, "Session", isolated_session), patch.object(alerts, "send_test_email", capture):
            uid, _ = account("no-contact")
            request = uuid4()
            result = alerts.create_alert(uid, request, demonstration=True)
            check("missing contact is recorded honestly", result["alert"]["status"] == "blocked_no_contact" and not captured)
            again = alerts.create_alert(uid, request, demonstration=True)
            check("same request is idempotent even without contact", result == again and connection.scalar(select(func.count()).select_from(SafetyAlert)) == 1)
            check("event payload contains only identifier and status", set(result) == {"event_id", "alert"} and set(result["alert"]) == {"status", "message"})

            for contact_status in ("pending", "declined", "revoked"):
                other, _ = account("contact-" + contact_status, contact_status=contact_status)
                check(contact_status + " contact cannot receive notification", alerts.create_alert(other, uuid4())["alert"]["status"] == "blocked_unconfirmed")

            missing, _ = account("no-permission", contact_status="confirmed", consent=False)
            check("confirmed contact without permissions is blocked", alerts.create_alert(missing, uuid4())["alert"]["status"] == "blocked_consent")
            live, _ = account("live-email", contact_status="confirmed", email="nobody@invalid.example")
            check("real/non-test recipient never sent", alerts.create_alert(live, uuid4())["alert"]["status"] == "blocked_live_not_configured" and not captured)

            confirmed, cid = account("confirmed", contact_status="confirmed")
            request, conversation_id = uuid4(), uuid4()
            result = alerts.create_alert(confirmed, request, conversation_id=conversation_id, demonstration=True)
            check("confirmed fictional contact captures local synthetic email", result["alert"]["status"] == "local_test_captured" and len(captured) == 1)
            email = captured[-1]
            check("capture is restricted to fictional recipient", email["recipient"] == "confirmed.contact@example.com")
            check("body is fixed synthetic demonstration", email["body"] == alerts.TEST_BODY and "does not report a real emergency" in email["body"])
            check("no private names/account details in email body", "Synthetic private display name" not in email["body"] and "Synthetic trusted name" not in email["body"] and "confirmed@example.com" not in email["body"])
            check("conversation metadata is retained without text", connection.scalar(select(SafetyAlert.conversation_id).where(SafetyAlert.request_id == request)) == conversation_id)
            repeat = alerts.create_alert(confirmed, request)
            check("successful request replay never resends", repeat == result and len(captured) == 1)
            cooldown = alerts.create_alert(confirmed, uuid4())
            check("new request obeys contact cooldown", cooldown["alert"]["status"] == "blocked_cooldown" and len(captured) == 1)
            with isolated_session(connection) as db:
                db.execute(update(SafetyAlert).where(SafetyAlert.request_id == request).values(created_at=connection.scalar(select(func.clock_timestamp())) - timedelta(minutes=11)))
                db.commit()
            check("new request can capture after cooldown", alerts.create_alert(confirmed, uuid4())["alert"]["status"] == "local_test_captured" and len(captured) == 2)

            withdrawn, _ = account("withdrawn", contact_status="confirmed")
            with isolated_session(connection) as db:
                db.add(Consent(user_id=withdrawn, consent_type="contact_alert", notice_version=CONTACT_CONSENT_VERSION, notice_text="Synthetic withdrawal", decision="withdrawn", recorded_at=connection.scalar(select(func.clock_timestamp()))))
                db.commit()
            check("latest withdrawal blocks capture", alerts.create_alert(withdrawn, uuid4())["alert"]["status"] == "blocked_consent" and len(captured) == 2)

            stale, _ = account("stale", contact_status="confirmed")
            with isolated_session(connection) as db:
                db.add(Consent(user_id=stale, consent_type="wellness_use", notice_version="old-notice", notice_text="Synthetic old consent", decision="accepted", recorded_at=connection.scalar(select(func.clock_timestamp()))))
                db.commit()
            check("stale latest wellness notice blocks capture", alerts.create_alert(stale, uuid4())["alert"]["status"] == "blocked_consent" and len(captured) == 2)

            uncertain_uid, _ = account("uncertain", contact_status="confirmed")
            uncertain_request = uuid4()
            def capture_then_fail(**message):
                captured.append(message)
                raise alerts.TestEmailDeliveryError("Synthetic uncertain capture")
            with patch.object(alerts, "send_test_email", capture_then_fail):
                uncertain = alerts.create_alert(uncertain_uid, uncertain_request)
            check("transport failure is uncertain, not sent", uncertain["alert"]["status"] == "uncertain" and "Synthetic uncertain" not in uncertain["alert"]["message"])
            count = len(captured)
            check("uncertain request replay does not retry", alerts.create_alert(uncertain_uid, uncertain_request) == uncertain and len(captured) == count)
            check("uncertain contact capture still applies cooldown", alerts.create_alert(uncertain_uid, uuid4())["alert"]["status"] == "blocked_cooldown" and len(captured) == count)

            concurrent_uid, _ = account("in-flight", contact_status="confirmed")
            concurrent_request, nested_result = uuid4(), []
            def capture_with_replay(**message):
                captured.append(message)
                nested_result.append(alerts.create_alert(concurrent_uid, concurrent_request))
            with patch.object(alerts, "send_test_email", capture_with_replay):
                completed = alerts.create_alert(concurrent_uid, concurrent_request)
            check("replay during transport sees an unconfirmed claim", nested_result[0]["alert"]["status"] == "uncertain")
            check("in-flight replay uses same event and does not send twice", nested_result[0]["event_id"] == completed["event_id"] and len(captured) == count + 1)
            check("in-flight claim ultimately completes once", completed["alert"]["status"] == "local_test_captured")

            check("own event can be read", alerts.get_own_event(concurrent_uid, completed["event_id"]) == completed)
            try:
                alerts.get_own_event(uid, completed["event_id"])
                raise AssertionError("other account read must fail")
            except HTTPException as error:
                check("other account cannot read event status", error.status_code == 404)
            check("same request UUID is scoped to account", alerts.create_alert(uid, concurrent_request)["event_id"] != completed["event_id"])
            with patch.object(alerts, "Session", side_effect=OperationalError("synthetic database error", {}, None)):
                try:
                    alerts.create_alert(uid, uuid4())
                    raise AssertionError("DB failure must propagate")
                except OperationalError:
                    check("database failure propagates for truthful support fallback", True)
            check("no live SMS transport exists in alert path", "sms_service" not in Path(alerts.__file__).read_text(encoding="utf-8"))
            check("outer temporary-table transaction remains active", outer.is_active)
    finally:
        outer.rollback()
    after = {name:connection.scalar(text("SELECT count(*) FROM public." + name)) for name in before}
    check("public data unchanged", before == after)
    check("temporary tables rolled back", connection.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")) == 0)

print(f"Passed {len(checks)} local safety-outbox checks. Fake SMTP only; no real messages sent.")
for name in checks: print("PASS:", name)
