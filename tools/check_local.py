"""Read-only local demonstration checks. No records, messages or settings change.

Run with the backend virtual environment. Never prints secret values, phone
numbers, account records, transcripts, email bodies or raw provider errors.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx
from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env")


def local_json(path):
    # Fixed loopback origin; keys/tokens are never sent in these checks.
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        reply = client.get("http://127.0.0.1:8000" + path)
        reply.raise_for_status()
        return reply.json()


def main():
    checks = []
    def record(component, status, detail, required=False):
        checks.append(dict(component=component, status=status, detail=detail, required=required))
    try:
        if local_json("/health").get("status") != "ok":
            raise ValueError("Unexpected health response")
        record("FastAPI", "ready", "ENWEN responds on http://127.0.0.1:8000/", True)
    except (httpx.HTTPError, ValueError, AttributeError):
        record("FastAPI", "not_ready", "Start FastAPI from the backend folder with its virtual environment.", True)
    try:
        from database import engine
        from sqlalchemy import inspect, text
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
        expected = {"users", "consents", "browser_sessions", "mood_entries", "journal_entries",
                    "trusted_contacts", "trusted_contact_invitations", "wellness_resources",
                    "resource_bookmarks", "chat_conversations", "chat_turns", "deleted_chat_requests", "safety_alerts"}
        missing = sorted(expected - tables)
        record("PostgreSQL", "not_ready" if missing else "ready",
               "Missing tables: " + ", ".join(missing) if missing else "Connected; expected tables exist. No student records were read.", True)
    except Exception:
        record("PostgreSQL", "not_ready", "Connection/schema check failed. Check PostgreSQL and your private backend configuration.", True)
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            reply = client.get("http://127.0.0.1:11434/api/tags")
            reply.raise_for_status()
            installed = any(item.get("name") == "llama3.2:3b" for item in reply.json().get("models", []))
        ready = os.getenv("AI_PROVIDER", "").strip().lower() == "ollama" and installed
        record("Local Llama", "ready" if ready else "not_ready",
               "Local service and llama3.2:3b are available. Generation was not invoked." if ready
               else "Start Ollama, install llama3.2:3b and select AI_PROVIDER=ollama.", True)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        record("Local Llama", "not_ready", "Ollama is not responding on this computer. No cloud fallback was attempted.", True)
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            reply = client.get("http://127.0.0.1:8025/")
            reply.raise_for_status()
        record("Local test inbox", "ready", "Mailpit web page responds. No email records were read or sent.")
    except httpx.HTTPError:
        record("Local test inbox", "not_ready", "Start Docker Desktop and the existing enwen-mailpit container for local invitation tests.")
    record("Live trusted-contact SMS", "not_implemented",
           "Automatic live contact alerts are not connected. Separate Brevo/Twilio/Africa's Talking own-phone test connectors exist; this check never invokes them.")
    record("Real email", "not_verified",
           "A separate Brevo own-mailbox test connector exists. Sender/account setup and a deliberate live test are still required; existing invitations use local Mailpit only.")
    record("Phone installation", "not_verified",
           "PWA files exist; phone use still needs a reachable HTTPS deployment and real-device testing.")
    result = dict(local_core_ready=all(item["status"] == "ready" for item in checks if item["required"]), checks=checks,
                  scope="Read-only local checks only; not clinical evaluation, SMS delivery or a completion percentage.")
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        for item in checks:
            print(f"{item['component']}: {item['status']} - {item['detail']}")
        print("Local core ready:", "yes" if result["local_core_ready"] else "no")
        print(result["scope"])
    return 0 if result["local_core_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
