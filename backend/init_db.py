from sqlalchemy import inspect

from database import engine
from models import Base
from journal_models import JournalEntry
from trusted_contact_models import TrustedContact
from contact_invitation_models import TrustedContactInvitation
from resource_models import ResourceBookmark, WellnessResource
from init_resources import create_resources
from auth_session_models import BrowserSession
from chat_history_models import ChatConversation, ChatTurn, DeletedChatRequest
from safety_models import SafetyAlert


def create_tables():
    Base.metadata.create_all(bind=engine)

    table_names = inspect(engine).get_table_names()

    expected_tables = (
        "users",
        "browser_sessions",
        "chat_conversations",
        "chat_turns",
        "deleted_chat_requests",
        "safety_alerts",
        "consents",
        "mood_entries",
        "journal_entries",
        "trusted_contacts",
        "trusted_contact_invitations",
        "wellness_resources",
        "resource_bookmarks",
    )

    for name in expected_tables:
        if name not in table_names:
            raise RuntimeError(f"Table was not found: {name}")

        print(f"Confirmed table: {name}")
    create_resources()


if __name__ == "__main__":
    create_tables()
