"""Local operator-only role assignment. No public role-grant endpoint or default account."""
import argparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import engine
from models import User
from community_models import CommunityModerator
if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Grant or revoke review access to deliberately shared community content only.')
    parser.add_argument('--email',required=True);parser.add_argument('--confirm',action='store_true');parser.add_argument('--revoke',action='store_true');args=parser.parse_args()
    if not args.confirm:parser.error('Review the account and use --confirm. This does not grant access to private journals or chats.')
    with Session(engine) as db,db.begin():
        user=db.scalar(select(User).where(User.email==args.email.strip().lower()).with_for_update())
        if user is None:raise SystemExit('Create the intended account through registration first.')
        role=db.get(CommunityModerator,user.user_id)
        if args.revoke and role:db.delete(role)
        elif not args.revoke and not role:db.add(CommunityModerator(user_id=user.user_id))
    print('Community-only moderator access '+('revoked.' if args.revoke else 'recorded.'))
