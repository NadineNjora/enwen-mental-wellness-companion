from sqlalchemy import inspect

from database import engine
from models import Base
from journal_models import JournalEntry
from trusted_contact_models import TrustedContact


def create_tables():
    Base.metadata.create_all(bind=engine)

    table_names = inspect(engine).get_table_names()

    expected_tables = (
        "users",
        "consents",
        "mood_entries",
        "journal_entries",
        "trusted_contacts",
    )

    for name in expected_tables:
        if name not in table_names:
            raise RuntimeError(f"Table was not found: {name}")

        print(f"Confirmed table: {name}")


if __name__ == "__main__":
    create_tables()