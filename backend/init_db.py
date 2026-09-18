from sqlalchemy import inspect

from database import engine
from models import Base


def create_tables():
    Base.metadata.create_all(bind=engine)

    table_names = inspect(engine).get_table_names()
    for name in ("users", "consents", "mood_entries"):
        if name not in table_names:
            raise RuntimeError(f"Table was not found: {name}")

        print(f"Confirmed table: {name}")


if __name__ == "__main__":
    create_tables()