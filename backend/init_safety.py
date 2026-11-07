"""Add the local safety outbox only; never alter existing records."""
from database import engine
from safety_models import SafetyAlert


def create_safety_tables():
    SafetyAlert.__table__.create(bind=engine, checkfirst=True)


if __name__ == "__main__":
    create_safety_tables()
    print("Local support outbox table ready. Existing records preserved.")
