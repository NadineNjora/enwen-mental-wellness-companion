"""Owner-isolation and replay tests using PostgreSQL TEMPORARY tables only."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import chat_history as history
from authentication import AccountResponse, get_current_user
from chat_history_models import ChatConversation, ChatTurn
from database import engine
from models import User
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateIndex, CreateTable

app = FastAPI()
app.include_router(history.router)
checks = []
def check(name, value):
    assert value, name
    checks.append(name)

def rejected(name, status, action):
    try:
        action()
        raise AssertionError(name + " should reject")
    except HTTPException as error:
        check(name, error.status_code == status)

permission = {"consent_version":"synthetic-local-history-1", "consent_text":"Synthetic acknowledgement of private stored conversations.", "provider":"Ollama local synthetic"}
uid, other_uid = uuid4(), uuid4()
profiles = [AccountResponse(user_id=value, email=f"history-{number}@example.com", display_name="Synthetic Student", wellness_consent_current=True)
            for number, value in enumerate((uid, other_uid))]
current = [profiles[0]]
app.dependency_overrides[get_current_user] = lambda: current[0]
tables = [User.__table__, ChatConversation.__table__, ChatTurn.__table__]
with engine.connect() as connection:
    public_tables = set(inspect(connection).get_table_names(schema="public"))
    tracked = [table.name for table in tables if table.name in public_tables]
    before = {name:connection.scalar(text("SELECT count(*) FROM public." + name)) for name in tracked}
    connection.rollback()
    outer = connection.begin()
    try:
        connection.execute(text("SET LOCAL statement_timeout='5s'"))
        for table in tables:
            ddl = str(CreateTable(table).compile(dialect=connection.dialect)).replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1)
            connection.exec_driver_sql(ddl)
            for index in table.indexes: connection.execute(CreateIndex(index))
        connection.execute(text("SET LOCAL search_path=pg_temp,pg_catalog"))
        for table in tables:
            check("isolated temporary table: " + table.name, connection.scalar(text("SELECT relpersistence='t' AND relnamespace=pg_my_temp_schema() FROM pg_class WHERE oid=to_regclass(:name)"), {"name":table.name}) is True)
        def isolated_session(bind):
            assert bind is connection and outer.is_active
            return RealSession(bind=connection, join_transaction_mode="create_savepoint")
        with patch.object(history,"engine",connection), patch.object(history,"Session",isolated_session), TestClient(app) as client:
            with isolated_session(connection) as db:
                db.add_all([User(user_id=value, email=f"history-{number}@example.com", display_name="Synthetic Student", password_hash="not-a-real-hash") for number,value in enumerate((uid,other_uid))])
                db.commit()
            response = client.get("/chat/conversations")
            check("new account starts with empty history", response.status_code == 200 and response.json() == [])
            check("history response is never cached", response.headers.get("cache-control") == "no-store")
            rejected("new conversation requires a recorded processing notice",422,lambda:history.claim_turn(uid,uuid4(),"Synthetic message"))
            request_id = uuid4()
            first = history.claim_turn(uid,request_id,"Synthetic exam worries",**permission)
            cid = first["conversation_id"]
            check("first turn claims a private conversation", first["status"] == "pending" and not first["replayed"] and first["context"] == [])
            check("claim reports attempt start time", first["started_at"] is not None)
            rejected("pending replay cannot generate twice",409,lambda:history.claim_turn(uid,request_id,"Synthetic exam worries",**permission))
            rejected("same request id cannot change message",409,lambda:history.claim_turn(uid,request_id,"Different synthetic message",**permission))
            rejected("same conversation accepts one pending ordinary turn",409,lambda:history.claim_turn(uid,uuid4(),"A competing message",conversation_id=cid,**permission))
            source = [{"resource_id":"synthetic-reading", "title":"Synthetic resource", "publisher":"Synthetic publisher", "url":"https://example.com/reading"}]
            finished = history.finish_turn(uid,first["turn_id"],"Synthetic reflective reply",sources=source)
            check("completed user and assistant exchange stored",finished["status"] == "complete" and finished["reply"] == "Synthetic reflective reply")
            replay = history.claim_turn(uid,request_id,"Synthetic exam worries",conversation_id=cid,**permission)
            check("completed replay returns original result and sources",replay["replayed"] and replay["reply"] == finished["reply"] and replay["sources"] == source)
            again = history.finish_turn(uid,first["turn_id"],"Late replacement must not overwrite")
            check("duplicate finalisation cannot overwrite a saved reply",again["replayed"] and again["reply"] == "Synthetic reflective reply")
            next_turn = history.claim_turn(uid,uuid4(),"A fictional follow-up",conversation_id=cid,**{**permission,"consent_text":"New acknowledgement does not overwrite conversation snapshot."})
            check("server context restores saved exchange",next_turn["context"] == [{"role":"user","content":"Synthetic exam worries"},{"role":"assistant","content":"Synthetic reflective reply"}])
            check("original processing notice retained",connection.scalar(select(ChatConversation.consent_text)) == permission["consent_text"])
            history.finish_turn(uid,next_turn["turn_id"],"Another synthetic reply")
            check("ordinary conversation has no saved crisis disposition",history.latest_support(uid,cid) is None)
            # Separate owner records do not appear in the first account.
            theirs = history.claim_turn(other_uid,uuid4(),"Other account private test",**permission)
            history.finish_turn(other_uid,theirs["turn_id"],"Other account response")
            rows = client.get("/chat/conversations").json()
            check("conversation listing is owner-only",len(rows)==1 and rows[0]["conversation_id"]==cid)
            detail = client.get("/chat/conversations/"+cid)
            check("saved conversation readable after page reload",detail.status_code==200 and len(detail.json()["messages"])==4)
            check("read view identifies role and sources",{m["role"] for m in detail.json()["messages"]}=={"user","assistant"} and any(m["sources"]==source for m in detail.json()["messages"]))
            check("detail response is never cached",detail.headers.get("cache-control")=="no-store")
            check("unknown conversation is 404",client.get("/chat/conversations/"+str(uuid4())).status_code==404)
            check("another user's conversation is indistinguishable 404",client.get("/chat/conversations/"+theirs["conversation_id"]).status_code==404)
            rejected("another user's conversation cannot be continued",404,lambda:history.claim_turn(uid,uuid4(),"Attempted wrong owner",conversation_id=theirs["conversation_id"],**permission))
            rejected("another user's turn cannot be finalised",404,lambda:history.finish_turn(uid,theirs["turn_id"],"Wrong owner"))
            rejected("another user's turn cannot be marked failed",404,lambda:history.fail_turn(uid,theirs["turn_id"]))
            rejected("saved support lookup cannot cross accounts",404,lambda:history.latest_support(uid,theirs["conversation_id"]))
            rejected("unknown support conversation is 404",404,lambda:history.latest_support(uid,uuid4()))
            page = client.get("/chat/conversations/"+cid+"?limit=1").json()
            check("turn pagination is bounded and advertises more",len(page["messages"])==2 and page["has_more"] is True)
            page2 = client.get("/chat/conversations/"+cid+"?limit=1&offset=1").json()
            check("last history page has no false continuation",len(page2["messages"])==2 and page2["has_more"] is False)
            check("invalid paging rejected",client.get("/chat/conversations?limit=101").status_code==422 and client.get("/chat/conversations?offset=-1").status_code==422)
            # Store failure without invented assistant/provider exception details.
            failed_id = uuid4()
            failed = history.claim_turn(uid,failed_id,"Synthetic unavailable-model attempt",**permission)
            history.fail_turn(uid,failed["turn_id"])
            rejected("failed replay never automatically generates again",503,lambda:history.claim_turn(uid,failed_id,"Synthetic unavailable-model attempt",**permission))
            failed_detail = client.get("/chat/conversations/"+failed["conversation_id"]).json()
            check("failed attempt shows the user message without invented AI text",len(failed_detail["messages"])==1 and failed_detail["messages"][0]["status"]=="failed")
            # Urgent turn interrupts an ordinary request already in flight.
            ordinary = history.claim_turn(uid,uuid4(),"Ordinary synthetic pending request",conversation_id=cid,**permission)
            crisis_id=uuid4()
            urgent = history.claim_turn(uid,crisis_id,"Synthetic immediate-danger test",conversation_id=cid,safety_event=True,**permission)
            check("urgent claim immediately pauses conversation",connection.scalar(select(ChatConversation.safety_paused).where(ChatConversation.conversation_id==cid)) is True)
            safety = {"level":"urgent", "alert":{"status":"not_configured"}, "contacts":[{"name":"Synthetic support"}]}
            crisis = history.finish_turn(uid,urgent["turn_id"],"Synthetic urgent support response",status="crisis",safety_payload=safety)
            check("crisis result preserves exact safety and alert disposition",crisis["status"]=="crisis" and crisis["safety"]==safety)
            latest = history.latest_support(uid,cid)
            check("latest saved support contains complete replayable result",latest["turn_id"]==urgent["turn_id"] and latest["conversation_id"]==cid
                  and latest["reply"]=="Synthetic urgent support response" and latest["safety"]==safety
                  and latest["sources"]==[] and latest["replayed"] is True)
            with isolated_session(connection) as db:
                db.add(ChatTurn(user_id=uid,request_id=uuid4(),conversation_id=cid,user_text="Older synthetic crisis",
                               assistant_text="Older synthetic support",status="crisis",sources=[],safety_payload={"level":"older"},
                               created_at=datetime(2020,1,1,tzinfo=timezone.utc)))
                db.commit()
            check("saved support lookup selects most recent crisis by creation time",history.latest_support(uid,cid)["turn_id"]==urgent["turn_id"])
            rejected("late ordinary reply suppressed after crisis pause",409,lambda:history.finish_turn(uid,ordinary["turn_id"],"Stale ordinary response"))
            history.fail_turn(uid,ordinary["turn_id"])
            repeated = history.claim_turn(uid,crisis_id,"Synthetic immediate-danger test",conversation_id=cid,**permission)
            check("crisis replay returns stored safety without repeating alert",repeated["replayed"] and repeated["safety"]==safety)
            rejected("paused conversation cannot resume normal generation",409,lambda:history.claim_turn(uid,uuid4(),"Resume ordinary conversation",conversation_id=cid,**permission))
            check("stale ordinary reply never saved",connection.scalar(select(ChatTurn.assistant_text).where(ChatTurn.turn_id==ordinary["turn_id"])) is None)
            # A new owner context budget cannot exceed the local connector's cap.
            long = history.claim_turn(uid,uuid4(),"x"*2000,**permission)
            history.finish_turn(uid,long["turn_id"],"y"*3000)
            long2=history.claim_turn(uid,uuid4(),"z"*2000,conversation_id=long["conversation_id"],**permission)
            check("server context fits bounded local model input",sum(len(item["content"]) for item in long2["context"])+2000<=6000)
            history.fail_turn(uid,long2["turn_id"])
            for bad in (" ","a"*2001,"bad\x00text"):
                rejected("invalid message text rejected: "+str(len(bad)),422,lambda:history.claim_turn(uid,uuid4(),bad,**permission))
            current[0].wellness_consent_current=False
            check("withdrawn consent blocks history listing",client.get("/chat/conversations").status_code==403)
            check("withdrawn consent blocks stored conversation read",client.get("/chat/conversations/"+cid).status_code==403)
            current[0].wellness_consent_current=True
            app.dependency_overrides.clear()
            check("anonymous history denied",client.get("/chat/conversations").status_code==401)
            check("outer transaction remains active",outer.is_active)
    finally:
        outer.rollback()
    after={name:connection.scalar(text("SELECT count(*) FROM public."+name)) for name in tracked}
    check("all pre-existing public record counts preserved",before==after)
    check("temporary history tables rolled back",connection.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'"))==0)
print(f"Passed {len(checks)} chat-history checks. No real conversations, model calls or alerts were created.")
for name in checks: print("PASS:",name)
