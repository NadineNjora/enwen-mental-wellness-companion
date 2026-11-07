"""Run from ENWEN/backend with its virtualenv. Uses TEMP tables and fake email."""

import hashlib
import importlib.util
import json
import re
import secrets
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateIndex, CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import authentication
import registration
from database import engine
from main import validation_error_handler
from models import Base, Consent, User
from contact_invitation_models import TrustedContactInvitation as Invitation
from trusted_contact_models import TrustedContact as Contact

spec = importlib.util.spec_from_file_location(
    "guided_invitations", Path(__file__).resolve().parents[1] / "backend" / "contacts_invitations.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

app = FastAPI()
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(registration.router)
app.include_router(authentication.router)
app.include_router(module.router)

passed = []
captured = []


def check(name, condition):
    assert condition, name
    passed.append(name)


def capture(**message):
    captured.append(message)


def get_token():
    return re.search(r"#token=([A-Za-z0-9_-]{43})", captured[-1]["body"])[1]


def counts(connection):
    return {
        name: connection.scalar(text("SELECT count(*) FROM public." + name))
        for name in sorted(Base.metadata.tables)
    }


connection = engine.connect()
before = counts(connection)
connection.rollback()
outer = connection.begin()
failure = None
try:
    connection.execute(text("SET LOCAL statement_timeout = '5s'"))
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=connection.dialect))
        connection.exec_driver_sql(ddl.replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1))
    connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))
    for table in Base.metadata.sorted_tables:
        check("isolated table: " + table.name, connection.scalar(text(
            "SELECT relpersistence='t' AND relnamespace=pg_my_temp_schema() "
            "FROM pg_class WHERE oid=to_regclass(:name)"
        ), {"name": table.name}) is True)
        for index in table.indexes:
            connection.execute(CreateIndex(index))

    def test_session(bind, *args, **kwargs):
        assert bind is connection and outer.is_active
        return RealSession(bind=connection, join_transaction_mode="create_savepoint")

    with ExitStack() as stack:
        for target in (module, authentication, registration):
            stack.enter_context(patch.object(target, "engine", connection))
            stack.enter_context(patch.object(target, "Session", test_session))
        stack.enter_context(patch.object(module, "send_test_email", capture))
        client = stack.enter_context(TestClient(app))
        password = secrets.token_urlsafe(24)
        password_hash = registration.password_hasher.hash(password)
        acknowledgement = {
            "notice_version": module.NOTICE_VERSION,
            "test_only_acknowledged": True,
        }

        def account(label, *, domain="example.com", contact=True):
            uid = uuid4()
            cid = uuid4()
            email = "isolated-" + label + "@example.com"
            connection.execute(insert(User).values(
                user_id=uid, email=email, display_name="Synthetic Student",
                password_hash=password_hash,
            ))
            for kind, version in (("wellness_use", registration.CONSENT_VERSION),
                                  ("contact_alert", registration.CONTACT_CONSENT_VERSION)):
                connection.execute(insert(Consent).values(
                    user_id=uid, consent_type=kind, notice_version=version,
                    notice_text="Temporary fixture, no real permission or personal information.",
                    decision="accepted",
                ))
            if contact:
                connection.execute(insert(Contact).values(
                    contact_id=cid, user_id=uid, full_name="Fictional Contact",
                    email="contact-" + label + "@" + domain,
                ))
            login = client.post("/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200
            return uid, cid, {"Authorization": "Bearer " + login.json()["access_token"]}

        def send(headers):
            return client.post("/trusted-contact/invitations", headers=headers, json=acknowledgement)

        def respond(token, decision="accepted", **overrides):
            return client.post("/trusted-contact/invitations/respond", json={
                **acknowledgement, "token": token, "decision": decision, **overrides,
            })

        notice = client.get("/trusted-contact/invitation-notice")
        check("notice is local-only and not cached", notice.status_code == 200
              and notice.json()["delivery_mode"] == "local_test"
              and notice.headers.get("cache-control") == "no-store")
        check("anonymous contact view denied", client.get("/trusted-contact").status_code == 401)
        check("anonymous send denied", send({}).status_code == 401)
        # Match the completed two-step frontend payload without saving public rows.
        registration_payload = {
            "email": "two-step@example.com", "display_name": "Two-step Student",
            "password": password, "consent_accepted": True,
            "consent_version": registration.CONSENT_VERSION,
            "trusted_contact": {"full_name": "Fictional Friend", "email": "two-step-friend@example.com", "relationship_label": "Friend"},
            "contact_consent_accepted": True,
            "contact_consent_version": registration.CONTACT_CONSENT_VERSION,
        }
        registered = client.post("/auth/register", json=registration_payload)
        check("two-step registration payload accepted", registered.status_code == 201)
        registered_user = connection.scalar(select(User.user_id).where(User.email == "two-step@example.com"))
        check("registration creates one user", registered_user is not None and connection.scalar(select(func.count()).select_from(User)) == 1)
        check("registration stores both consents", connection.scalar(select(func.count()).select_from(Consent).where(Consent.user_id == registered_user)) == 2)
        check("registration contact remains pending", connection.scalar(select(Contact.confirmation_status).where(Contact.user_id == registered_user)) == "pending")
        check("registration sends no invitation", len(captured) == 0 and connection.scalar(select(func.count()).select_from(Invitation)) == 0)
        check("duplicate registration rejected", client.post("/auth/register", json=registration_payload).status_code == 409)
        incomplete = {key: value for key, value in registration_payload.items() if key != "trusted_contact"}
        incomplete["email"] = "incomplete@example.com"
        check("missing second step rejected", client.post("/auth/register", json=incomplete).status_code == 422)
        refused = {**registration_payload, "email": "refused@example.com", "contact_consent_accepted": False}
        check("contact permission required", client.post("/auth/register", json=refused).status_code == 400)
        check("failed registration creates no partial rows", connection.scalar(select(func.count()).select_from(User)) == 1 and connection.scalar(select(func.count()).select_from(Contact)) == 1 and connection.scalar(select(func.count()).select_from(Consent)) == 2)
        uid, cid, headers = account("owner")
        other_uid, other_cid, other_headers = account("other")
        check("contact view is owner-only", client.get("/trusted-contact", headers=other_headers).json()["email"] == "contact-other@example.com")
        check("GET cannot consume invitation", client.get("/trusted-contact/invitations/respond").status_code == 405)
        for body, expected, label in (
            ({**acknowledgement, "test_only_acknowledged": False}, 400, "test acknowledgement required"),
            ({**acknowledgement, "test_only_acknowledged": "true"}, 422, "test acknowledgement is strict boolean"),
            ({**acknowledgement, "notice_version": "old"}, 409, "stale notice rejected"),
            ({**acknowledgement, "user_id": str(other_uid)}, 422, "cannot choose another account in send payload"),
        ):
            check(label, client.post("/trusted-contact/invitations", headers=headers, json=body).status_code == expected)
        _, _, gmail = account("external", domain="gmail.com")
        check("Gmail status explains blocked delivery", client.get("/trusted-contact", headers=gmail).json()["can_invite"] is False)
        check("Gmail invitations rejected", send(gmail).status_code == 400)
        legacy_uid, _, legacy = account("legacy", contact=False)
        check("missing contact reported without creating one", send(legacy).status_code == 404)
        connection.execute(delete(Consent).where(Consent.user_id == legacy_uid, Consent.consent_type == "contact_alert"))
        setup_payload = {"trusted_contact": {"full_name": "Legacy Friend", "email": "legacy-friend@example.com", "relationship_label": "Friend"}, "contact_consent_accepted": True, "contact_consent_version": registration.CONTACT_CONSENT_VERSION}
        check("anonymous contact setup denied", client.post("/trusted-contact", json=setup_payload).status_code == 401)
        check("contact setup requires explicit consent", client.post("/trusted-contact", headers=legacy, json={**setup_payload, "contact_consent_accepted": False}).status_code == 400)
        check("contact setup rejects stale notice", client.post("/trusted-contact", headers=legacy, json={**setup_payload, "contact_consent_version": "old"}).status_code == 409)
        self_payload = {**setup_payload, "trusted_contact": {"full_name": "Self", "email": "ISOLATED-LEGACY@example.com"}}
        check("contact setup rejects self email", client.post("/trusted-contact", headers=legacy, json=self_payload).status_code == 400)
        check("contact setup cannot select another user", client.post("/trusted-contact", headers=legacy, json={**setup_payload, "user_id": str(uid)}).status_code == 422)
        setup_result = client.post("/trusted-contact", headers=legacy, json=setup_payload)
        check("older account can add a pending person", setup_result.status_code == 201 and setup_result.json()["confirmation_status"] == "pending")
        check("setup records contact permission once", connection.scalar(select(func.count()).select_from(Consent).where(Consent.user_id == legacy_uid, Consent.consent_type == "contact_alert")) == 1)
        check("setup saves person to the correct account", client.get("/trusted-contact", headers=legacy).json()["email"] == "legacy-friend@example.com")
        check("duplicate setup never overwrites person", client.post("/trusted-contact", headers=legacy, json=setup_payload).status_code == 409)
        check("setup cannot replace another account's contact", client.post("/trusted-contact", headers=headers, json=setup_payload).status_code == 409)
        check("setup sends no invitation or alert", len(captured) == 0 and connection.scalar(select(func.count()).select_from(Invitation)) == 0)
        check("rejected requests send no email", len(captured) == 0)

        response = send(headers)
        check("invitation capture returns 201", response.status_code == 201)
        token = get_token()
        check("token is not returned in API response", token not in response.text)
        check("token is in fragment, not query string", "contacts_response.html#token=" in captured[-1]["body"] and "?token=" not in captured[-1]["body"])
        check("email contains no account email or wellness records", "isolated-owner@example.com" not in captured[-1]["body"])
        stored = connection.execute(select(Invitation).where(Invitation.contact_id == cid)).mappings().one()
        check("only token digest stored", stored["token_hash"] == hashlib.sha256(token.encode()).hexdigest() and stored["token_hash"] != token)
        check("link lasts 24 hours", stored["expires_at"] - stored["created_at"] == timedelta(hours=24))
        check("capture leaves contact pending", client.get("/trusted-contact", headers=headers).json()["confirmation_status"] == "pending")
        check("cooldown visible in status", client.get("/trusted-contact", headers=headers).json()["retry_after_seconds"] > 0 and not client.get("/trusted-contact", headers=headers).json()["can_invite"])
        check("pending invitation visible", client.get("/trusted-contact", headers=headers).json()["latest_invitation"]["status"] == "awaiting_response")
        check("rapid resend blocked", send(headers).status_code == 429 and len(captured) == 1)
        check("unknown token rejected", respond("z" * 43).status_code == 410)
        check("response requires notice acknowledgement", respond(token, test_only_acknowledged=False).status_code == 400)
        check("response requires current notice", respond(token, notice_version="old").status_code == 409)
        bad = respond("private-test-value")
        check("validation does not echo token", bad.status_code == 422 and "private-test-value" not in bad.text and all("input" not in e for e in bad.json()["detail"]))
        response = respond(token)
        check("acceptance succeeds", response.status_code == 200 and response.json()["confirmation_status"] == "confirmed")
        check("confirmed status disables sending", client.get("/trusted-contact", headers=headers).json()["can_invite"] is False)
        check("acceptance never enables live alerts", response.json()["live_notifications_enabled"] is False)
        check("acceptance response not cached", response.headers.get("cache-control") == "no-store")
        check("confirmation time saved", connection.scalar(select(Contact.confirmed_at).where(Contact.contact_id == cid)) is not None)
        check("used link cannot change decision", respond(token, "declined").status_code == 410)
        check("confirmed contact not reinvited", send(headers).status_code == 409)
        check("other contact remains pending", client.get("/trusted-contact", headers=other_headers).json()["confirmation_status"] == "pending")

        check("second account can send own invite", send(other_headers).status_code == 201)
        decline_token = get_token()
        response = respond(decline_token, "declined")
        check("decline succeeds", response.status_code == 200 and response.json()["confirmation_status"] == "declined")
        check("decline has no confirmed timestamp", connection.scalar(select(Contact.confirmed_at).where(Contact.contact_id == other_cid)) is None)
        check("declined contact not reinvited", send(other_headers).status_code == 409)

        _, expired_cid, expired_headers = account("expired")
        assert send(expired_headers).status_code == 201
        expired_token = get_token()
        now = connection.scalar(select(func.clock_timestamp()))
        connection.execute(update(Invitation).where(Invitation.contact_id == expired_cid).values(
            created_at=now-timedelta(days=2), expires_at=now-timedelta(days=1),
        ))
        check("expired token rejected", respond(expired_token).status_code == 410)
        check("expired invite can be replaced", send(expired_headers).status_code == 201)
        replacement_token = get_token()
        check("replacement differs", replacement_token != expired_token)
        check("old link remains unusable after replacement", respond(expired_token).status_code == 410)
        check("replacement link works", respond(replacement_token).status_code == 200)

        revoked_uid, revoked_cid, revoked_headers = account("withdrawn")
        assert send(revoked_headers).status_code == 201
        withdrawn_token = get_token()
        connection.execute(insert(Consent).values(
            user_id=revoked_uid, consent_type="contact_alert",
            notice_version=registration.CONTACT_CONSENT_VERSION,
            notice_text="Synthetic withdrawal", decision="withdrawn",
            recorded_at=connection.scalar(select(func.clock_timestamp())),
        ))
        check("latest withdrawn consent blocks response", respond(withdrawn_token).status_code == 403)
        check("withdrawn consent disables button eligibility", client.get("/trusted-contact", headers=revoked_headers).json()["can_invite"] is False)
        check("latest withdrawn consent blocks sending", send(revoked_headers).status_code == 403)
        check("withdrawal does not silently confirm contact", connection.scalar(select(Contact.confirmation_status).where(Contact.contact_id == revoked_cid)) == "pending")

        _, failed_cid, failed_headers = account("failure")
        with patch.object(module, "send_test_email", side_effect=module.TestEmailDeliveryError("Synthetic failure")):
            response = send(failed_headers)
        check("SMTP failure is handled safely", response.status_code == 503 and "Synthetic failure" not in response.text)
        check("failed send leaves no invitation row", connection.scalar(select(func.count()).select_from(Invitation).where(Invitation.contact_id == failed_cid)) == 0)

        _, retry_cid, retry_headers = account("retry")
        assert send(retry_headers).status_code == 201
        old_token = get_token()
        connection.execute(update(Invitation).where(Invitation.contact_id == retry_cid).values(
            created_at=connection.scalar(select(func.clock_timestamp()))-timedelta(seconds=70),
        ))
        def capture_then_fail(**message):
            capture(**message)
            raise module.TestEmailDeliveryError("Uncertain capture")
        with patch.object(module, "send_test_email", capture_then_fail):
            response = send(retry_headers)
        failed_token = get_token()
        check("uncertain replacement returns failure", response.status_code == 503)
        check("uncertain replacement token is invalid", respond(failed_token).status_code == 410)
        check("previous valid link survives failed replacement", respond(old_token).status_code == 200)
        check("outer test transaction still active", outer.is_active)
except Exception as error:
    failure = {"type": type(error).__name__, "check": str(error) if isinstance(error, AssertionError) else "Details withheld to avoid exposing settings."}
finally:
    if outer.is_active:
        outer.rollback()
    after = counts(connection)
    check("public record counts unchanged", before == after)
    check("temporary tables rolled back", connection.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")) == 0)
    connection.close()

print(json.dumps({"passed": len(passed), "checks": passed, "failure": failure,
                  "email_transport": "fake; no messages sent", "target": "project backend/contacts_invitations.py"}, indent=2))
if failure:
    raise SystemExit(1)
