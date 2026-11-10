"""Add community tables without changing private journal or existing account data."""
from database import engine
from community_models import CommunityModerator,CommunityPost,CommunityFeedback,CommunityReport,CommunityReview,CommunityReplyRead
def create_community():
    for model in (CommunityModerator,CommunityPost,CommunityFeedback,CommunityReport,CommunityReview,CommunityReplyRead):model.__table__.create(bind=engine,checkfirst=True)
if __name__=='__main__':
    create_community();print('Community tables confirmed. Private journals, moods and chats were not changed.')
