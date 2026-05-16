from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    is_owner = Column(Boolean, default=False)

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(Integer, primary_key=True)
    channel_id = Column(BigInteger, unique=True, nullable=False)
    title = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class CustomEmoji(Base):
    __tablename__ = 'custom_emojis'
    id = Column(Integer, primary_key=True)
    custom_emoji_id = Column(String, unique=True, nullable=False)
    shortcut = Column(String, nullable=True) # Optional shortcut text

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    creator_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=True) # Target channel
    text = Column(Text, nullable=True)
    media_file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True) # photo, video, etc.
    entities_json = Column(Text, nullable=True) # Store JSON of entities
    preview_message_id = Column(BigInteger, nullable=True)
    preview_chat_id = Column(BigInteger, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot_database.db")
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
