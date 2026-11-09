"""Operator-only public-resource role assignment, independent of community roles."""
import argparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import engine
from models import User
from resource_admin_models import ResourceCurator
if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Grant or revoke public resource draft, publish and retirement access only.')
    parser.add_argument('--email',required=True);parser.add_argument('--confirm',action='store_true');parser.add_argument('--revoke',action='store_true');args=parser.parse_args()
    if not args.confirm:parser.error('Review the account and use --confirm. This role changes public resources and the AI summary corpus, not student records.')
    with Session(engine) as db,db.begin():
        user=db.scalar(select(User).where(User.email==args.email.strip().lower()).with_for_update())
        if not user:raise SystemExit('The intended account must already exist.')
        role=db.get(ResourceCurator,user.user_id)
        if args.revoke and role:db.delete(role)
        elif not args.revoke and not role:db.add(ResourceCurator(user_id=user.user_id))
    print('Public-resource curator role '+('revoked.' if args.revoke else 'recorded.'))
