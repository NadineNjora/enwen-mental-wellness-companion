"""Create only missing chat-history tables; preserve all existing records."""
from chat_history_models import ChatConversation, ChatTurn
from database import engine


if __name__ == "__main__":
    for table in (ChatConversation.__table__, ChatTurn.__table__):
        table.create(bind=engine, checkfirst=True)
    print("Private chat-history tables ready. Existing records preserved.")
