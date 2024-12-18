from sqlalchemy import create_engine, Column, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
from config import SQLALCHEMY_DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# チャットを保存するテーブルの定義
class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.now)
    messages = relationship("Message", back_populates="chat")

# チャットのメッセージを保存するテーブルの定義
# チャットに対して1対多の関係を持つ
class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String, ForeignKey("chats.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    chat = relationship("Chat", back_populates="messages")

# メニューテーブルの定義
class Menu(Base):
    __tablename__ = "menus"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True)
    ingredients = Column(Text)  # JSON文字列やカンマ区切りでも可
    allergies = Column(Text)     # アレルギー情報
    is_halal = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()