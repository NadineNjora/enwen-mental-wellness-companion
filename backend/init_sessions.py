"""Add only the browser-session table; leave all existing records untouched."""
from auth_session_models import BrowserSession
from database import engine

if __name__ == "__main__":
    BrowserSession.__table__.create(bind=engine, checkfirst=True)
    print("Browser-session table ready. Existing records preserved.")
