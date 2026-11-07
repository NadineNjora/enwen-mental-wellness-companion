"""Persistent login tests using PostgreSQL temporary tables, no real accounts."""
import hashlib
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import authentication as auth
from auth_session_models import BrowserSession
from database import engine
from models import User, Consent
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable, CreateIndex
import jwt

app = FastAPI()
app.include_router(auth.router)
tables = [User.__table__, Consent.__table__, BrowserSession.__table__]
checks = []
def check(name, value):
    assert value, name
    checks.append(name)

with engine.connect() as connection:
    before = {table.name: connection.scalar(text("SELECT count(*) FROM public." + table.name)) for table in tables}
    connection.rollback()
    transaction = connection.begin()
    try:
        for table in tables:
            ddl = str(CreateTable(table).compile(dialect=connection.dialect)).replace("CREATE TABLE ", "CREATE TEMPORARY TABLE ", 1)
            connection.exec_driver_sql(ddl)
            for index in table.indexes: connection.execute(CreateIndex(index))
        connection.execute(text("SET LOCAL search_path = pg_temp, pg_catalog"))
        def isolated_session(bind):
            assert bind is connection
            return Session(bind=connection, join_transaction_mode="create_savepoint")
        with patch.object(auth, "engine", connection), patch.object(auth, "Session", isolated_session):
            uid, password = uuid4(), secrets.token_urlsafe(24)
            with isolated_session(connection) as db:
                db.add(User(user_id=uid, email="session-test@example.com", display_name="Session Test", password_hash=auth.password_hasher.hash(password)))
                db.commit()
            with TestClient(app) as client:
                invalid = client.post("/auth/login", json={"email":"session-test@example.com", "password":"incorrect"})
                check("failed login creates no saved cookie", invalid.status_code == 401 and not client.cookies)
                login = client.post("/auth/login", json={"email":"session-test@example.com", "password":password})
                check("login succeeds", login.status_code == 200)
                cookie = login.headers["set-cookie"].lower()
                check("saved cookie is HttpOnly, SameSite Strict, scoped to auth", "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie)
                secret = client.cookies.get(auth.SESSION_COOKIE)
                stored = connection.scalar(select(BrowserSession.token_hash))
                check("only hash stored in database", secret != stored and stored == hashlib.sha256(secret.encode()).hexdigest())
                token = login.json()["access_token"]
                check("access token remains 15 minutes", login.json()["expires_in"] == 900)
                check("account request works", client.get("/auth/me", headers={"Authorization":"Bearer " + token}).status_code == 200)
                with TestClient(app) as reloaded:
                    reloaded.cookies.update(client.cookies)
                    restored = reloaded.post("/auth/session")
                    check("fresh browser page restores login without password", restored.status_code == 200 and bool(restored.json()["access_token"]))
                bad_origin = client.post("/auth/session", headers={"Origin":"https://unrelated.example"})
                check("foreign origin cannot renew", bad_origin.status_code == 403)
                check("foreign origin cannot logout", client.post("/auth/logout", headers={"Origin":"https://unrelated.example"}).status_code == 403)
                check("logout succeeds", client.post("/auth/logout").status_code == 204)
                check("logout removes cookie", not client.cookies.get(auth.SESSION_COOKIE))
                check("logout revokes issued access token", client.get("/auth/me", headers={"Authorization":"Bearer " + token}).status_code == 401)
                check("logout prevents refresh", client.post("/auth/session").status_code == 401)
                client.cookies.set(auth.SESSION_COOKIE, secret, path="/auth")
                check("copied revoked cookie rejected", client.post("/auth/session").status_code == 401)
                client.cookies.clear()
                client.post("/auth/login", json={"email":"session-test@example.com", "password":password})
                connection.execute(update(BrowserSession).values(expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
                check("expired saved session rejected", client.post("/auth/session").status_code == 401)
                client.cookies.clear()
                client.post("/auth/login", json={"email":"session-test@example.com", "password":password})
                connection.execute(update(BrowserSession).values(absolute_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
                check("absolute expiry cannot be renewed", client.post("/auth/session").status_code == 401)
            with TestClient(app, base_url="https://testserver") as tls_client:
                secured = tls_client.post("/auth/login", json={"email":"session-test@example.com", "password":password})
                check("HTTPS uses Secure cookie", "; secure" in secured.headers["set-cookie"].lower())
    finally:
        transaction.rollback()
    after = {table.name: connection.scalar(text("SELECT count(*) FROM public." + table.name)) for table in tables}
    check("existing public records untouched", before == after)
print(f"Passed {len(checks)} session checks; existing accounts untouched.")
for name in checks: print("PASS:", name)
