"""Rename/removal checks against rolled-back PostgreSQL TEMP tables only."""
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import chat_history as history
import chat_management as management
from authentication import AccountResponse, get_current_user
from chat_history_models import ChatConversation, ChatTurn, DeletedChatRequest
from database import engine
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from models import User
from safety_models import SafetyAlert
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql.dml import Delete
from trusted_contact_models import TrustedContact

app = FastAPI()
app.include_router(history.router)
app.include_router(management.router)
uids = [uuid4(), uuid4()]
current = [AccountResponse(user_id=uids[0], email="manage@example.com", display_name="Synthetic", wellness_consent_current=True)]
app.dependency_overrides[get_current_user] = lambda: current[0]
permission = dict(consent_version="synthetic-only", consent_text="Fictional acknowledgement", provider="fake-no-model")
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)
def rejects(name, code, action):
    try:
        action()
        raise AssertionError(name + " did not reject")
    except HTTPException as error:
        check(name, error.status_code == code)

tables = [User.__table__, TrustedContact.__table__, ChatConversation.__table__, ChatTurn.__table__, DeletedChatRequest.__table__, SafetyAlert.__table__]
with engine.connect() as connection:
    public = set(inspect(connection).get_table_names(schema="public"))
    tracked = [table.name for table in tables if table.name in public]
    before = {name:connection.scalar(text("SELECT count(*) FROM public." + name)) for name in tracked}
    connection.rollback()
    outer = connection.begin()
    try:
        connection.execute(text("SET LOCAL statement_timeout='5s'"))
        for table in tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1))
            for index in table.indexes: connection.execute(CreateIndex(index))
        connection.execute(text("SET LOCAL search_path=pg_temp,pg_catalog"))
        for table in tables:
            check("temporary isolation: " + table.name, connection.scalar(text("SELECT relpersistence='t' AND relnamespace=pg_my_temp_schema() FROM pg_class WHERE oid=to_regclass(:name)"), {"name":table.name}) is True)
        fail_delete = [False]
        def isolated_session(bind):
            assert bind is connection and outer.is_active
            db = RealSession(bind=connection, join_transaction_mode="create_savepoint")
            original = db.execute
            def execute(statement, *args, **kwargs):
                if fail_delete[0] and isinstance(statement, Delete): raise SQLAlchemyError("Synthetic failure")
                return original(statement, *args, **kwargs)
            db.execute = execute
            return db
        with ExitStack() as stack:
            for module in (history, management):
                stack.enter_context(patch.object(module, "engine", connection))
                stack.enter_context(patch.object(module, "Session", isolated_session))
            client = stack.enter_context(TestClient(app))
            with isolated_session(connection) as db:
                db.add_all(User(user_id=uid, email=f"manage-{i}@example.com", display_name="Synthetic", password_hash="unused") for i,uid in enumerate(uids))
                db.commit()
            request_id = uuid4()
            record = history.claim_turn(uids[0], request_id, "Fictional exam stress", **permission)
            cid = record["conversation_id"]
            url = "/chat/conversations/" + cid
            check("pending deletion blocked", client.delete(url).status_code == 409)
            check("refusal retains message and creates no replay guard", connection.scalar(select(func.count()).select_from(ChatTurn)) == 1 and connection.scalar(select(func.count()).select_from(DeletedChatRequest)) == 0)
            history.finish_turn(uids[0], record["turn_id"], "Synthetic saved reply")
            other = history.claim_turn(uids[1], request_id, "Other owner's message", **permission)
            history.finish_turn(uids[1], other["turn_id"], "Other owner's reply")
            foreign_url = "/chat/conversations/" + other["conversation_id"]
            check("other owner's rename denied", client.patch(foreign_url, json={"title":"Wrong owner"}).status_code == 404)
            check("other owner's deletion denied", client.delete(foreign_url).status_code == 404)
            check("unknown delete uses identical 404", client.delete("/chat/conversations/" + str(uuid4())).status_code == 404)
            check("invalid identifier rejected", client.delete("/chat/conversations/not-a-uuid").status_code == 422)
            for label, payload in (("blank", {"title":"   "}), ("long", {"title":"a"*81}), ("type", {"title":42}), ("control", {"title":"bad\x00name"}), ("extra owner", {"title":"Name", "user_id":str(uids[1])})):
                check("invalid name: " + label, client.patch(url, json=payload).status_code == 422)
            result = client.patch(url, json={"title":"  Exam   week 🌷  "})
            check("Unicode name saved with normalised spacing", result.status_code == 200 and result.json()["title"] == "Exam week 🌷")
            check("rename is no-store", result.headers.get("cache-control") == "no-store")
            check("rename preserves saved content", client.get(url).json()["messages"][1]["content"] == "Synthetic saved reply")
            current[0].wellness_consent_current = False
            check("withdrawal blocks further naming", client.patch(url, json={"title":"Changed"}).status_code == 403)
            fail_delete[0] = True
            failure = client.delete(url)
            fail_delete[0] = False
            check("database failure reported honestly", failure.status_code == 503 and "could not be confirmed" in failure.text)
            check("failed deletion rolls back content and guards", connection.scalar(select(func.count()).select_from(ChatTurn)) == 2 and connection.scalar(select(func.count()).select_from(DeletedChatRequest)) == 0)
            deleted = client.delete(url)
            check("deletion available after consent withdrawal", deleted.status_code == 204 and not deleted.content)
            check("deletion is no-store", deleted.headers.get("cache-control") == "no-store")
            current[0].wellness_consent_current = True
            check("removed conversation unreadable", client.get(url).status_code == 404)
            check("removed conversation unlisted", client.get("/chat/conversations").json() == [])
            check("active message content removed", connection.scalar(select(func.count()).select_from(ChatTurn).where(ChatTurn.user_id == uids[0])) == 0)
            check("content-free guard retained", set(DeletedChatRequest.__table__.columns.keys()) == {"user_id","request_id","deleted_at"} and connection.scalar(select(DeletedChatRequest.request_id).where(DeletedChatRequest.user_id == uids[0])) == request_id)
            rejects("stale request cannot recreate message", 410, lambda:history.claim_turn(uids[0], request_id, "Fictional exam stress", **permission))
            rejects("changed stale request blocked", 410, lambda:history.claim_turn(uids[0], request_id, "Changed text", **permission))
            rejects("stale conversation retry blocked", 410, lambda:history.claim_turn(uids[0], request_id, "Fictional exam stress", conversation_id=cid, **permission))
            rejects("new request cannot continue deleted thread", 404, lambda:history.claim_turn(uids[0], uuid4(), "New message", conversation_id=cid, **permission))
            check("repeat deletion harmless", client.delete(url).status_code == 404)
            replay = history.claim_turn(uids[1], request_id, "Other owner's message", **permission)
            check("other owner's same request ID unaffected", replay["replayed"] and replay["reply"] == "Other owner's reply")
            failed = history.claim_turn(uids[0], uuid4(), "Failed attempt", **permission)
            history.fail_turn(uids[0], failed["turn_id"])
            check("failed attempt removable", client.delete("/chat/conversations/" + failed["conversation_id"]).status_code == 204)
            urgent_id = uuid4()
            urgent = history.claim_turn(uids[0], urgent_id, "Synthetic safety test", safety_event=True, **permission)
            history.finish_turn(uids[0], urgent["turn_id"], "Synthetic support", status="crisis", safety_payload={"level":"urgent"})
            with isolated_session(connection) as db:
                event = SafetyAlert(user_id=uids[0], request_id=urgent_id, conversation_id=UUID(urgent["conversation_id"]), status="blocked_no_contact", demonstration=True)
                db.add(event); db.flush(); event_id = event.event_id; db.commit()
            urgent_url = "/chat/conversations/" + urgent["conversation_id"]
            check("rename never resumes paused thread", client.patch(urgent_url, json={"title":"Support"}).json()["safety_paused"] is True)
            check("completed support transcript removable", client.delete(urgent_url).status_code == 204)
            check("notification disposition preserved", connection.scalar(select(SafetyAlert.status).where(SafetyAlert.event_id == event_id)) == "blocked_no_contact")
            rejects("deleted urgent request cannot repeat alert", 410, lambda:history.claim_turn(uids[0], urgent_id, "Synthetic safety test", safety_event=True, **permission))
            check("notification count unchanged", connection.scalar(select(func.count()).select_from(SafetyAlert)) == 1)
            app.dependency_overrides.clear()
            check("anonymous delete denied", client.delete(foreign_url).status_code == 401)
            check("anonymous rename denied", client.patch(foreign_url, json={"title":"Attempt"}).status_code == 401)
            check("outer rollback available", outer.is_active)
    finally:
        outer.rollback()
    after = {name:connection.scalar(text("SELECT count(*) FROM public." + name)) for name in tracked}
    check("pre-existing public record counts preserved", before == after)
    check("TEMP tables rolled back", connection.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")) == 0)
print(f"Passed {len(checks)} chat-management checks. Only TEMP fictional records changed; no model or notification called.")
for name in checks: print("PASS:", name)
