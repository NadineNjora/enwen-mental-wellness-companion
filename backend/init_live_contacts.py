from database import engine
from live_contact_models import LiveContactInvitation

if __name__=="__main__":
    LiveContactInvitation.__table__.create(bind=engine,checkfirst=True)
    print("Real invitation table ready; existing contact-test records preserved.")
