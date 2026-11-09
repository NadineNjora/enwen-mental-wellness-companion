from sqlalchemy import inspect

from database import engine
from models import Base
from mood_context_models import MoodContext
from community_models import CommunityModerator,CommunityPost,CommunityFeedback,CommunityReport,CommunityReview
from resource_admin_models import ResourceCurator,ResourceDraft,ResourceAudit
from journal_models import JournalEntry
from trusted_contact_models import TrustedContact
from contact_invitation_models import TrustedContactInvitation
from resource_models import ResourceBookmark, WellnessResource
from init_resources import create_resources
from auth_session_models import BrowserSession
from chat_history_models import ChatConversation, ChatTurn, DeletedChatRequest
from safety_models import SafetyAlert
from live_contact_models import LiveContactInvitation
from knowledge import seed as seed_knowledge
from live_email_alerts import LiveEmailAlert, LiveEmailPermission


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
        "live_contact_invitations",
        "knowledge_passages",
        "live_email_alerts",
        "live_email_permissions",
        "consents",
        "mood_entries",
        "mood_contexts",
        "community_moderators",
        "community_posts",
        "community_feedback",
        "community_reports",
        "community_reviews",
        "resource_curators",
        "resource_drafts",
        "resource_audit",
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
    seed_knowledge()


if __name__ == "__main__":
    create_tables()
