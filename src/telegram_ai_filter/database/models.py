"""SQLAlchemy ORM models."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ContentType(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    NEWS = "NEWS"
    TUTORIAL = "TUTORIAL"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    COMPETITION = "COMPETITION"
    PRODUCT = "PRODUCT"
    SALE = "SALE"
    ADVERTISEMENT = "ADVERTISEMENT"
    MEME = "MEME"
    DISCUSSION = "DISCUSSION"
    OTHER = "OTHER"


class ImportanceLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackType(str, enum.Enum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    SAVED = "saved"
    MOVED = "moved"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- User Profile ---


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)

    # Explicit preferences (user-configured)
    interests = Column(Text, nullable=False, default="")
    excluded_topics = Column(Text, nullable=False, default="")

    # Settings
    min_ai_score = Column(Integer, nullable=False, default=70)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    digest_enabled = Column(Boolean, nullable=False, default=False)

    # AI settings
    ai_base_url = Column(String(500), nullable=True)
    ai_api_key = Column(String(500), nullable=True)
    ai_model = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")


# --- Folders ---


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    is_system = Column(Boolean, nullable=False, default=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("UserProfile", back_populates="folders")
    parent = relationship("Folder", remote_side=[id])
    posts = relationship("Post", back_populates="folder")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_folder_user_name"),
    )


# --- Telegram Sources ---


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    channel_id = Column(Integer, nullable=False)
    channel_username = Column(String(255), nullable=True)
    channel_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    added_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("UserProfile", back_populates="sources")
    posts = relationship("Post", back_populates="source")

    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_source_user_channel"),
    )


# --- Posts ---


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    telegram_message_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    channel_name = Column(String(255), nullable=False)
    channel_username = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    message_url = Column(String(500), nullable=True)
    has_photo = Column(Boolean, nullable=False, default=False)
    has_video = Column(Boolean, nullable=False, default=False)
    telegram_created_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=utcnow)

    source = relationship("Source", back_populates="posts")
    analysis = relationship("Analysis", back_populates="post", uselist=False, cascade="all, delete-orphan")
    folder = relationship("Folder", back_populates="posts")
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    feedbacks = relationship("Feedback", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("channel_id", "telegram_message_id", name="uq_post_telegram"),
    )


# --- AI Analysis Results ---


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), unique=True, nullable=False)
    useful = Column(Boolean, nullable=False)
    score = Column(Integer, nullable=False)
    category = Column(String(255), nullable=False)
    subcategory = Column(String(255), nullable=True)
    content_type = Column(Enum(ContentType), nullable=False, default=ContentType.OTHER)
    importance = Column(Enum(ImportanceLevel), nullable=False, default=ImportanceLevel.MEDIUM)
    reason = Column(Text, nullable=False)
    suggested_folder = Column(String(255), nullable=True)
    processed_at = Column(DateTime, nullable=False, default=utcnow)

    post = relationship("Post", back_populates="analysis")


# --- Feedback ---


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    feedback_type = Column(Enum(FeedbackType), nullable=False)
    reason = Column(String(255), nullable=True)
    target_folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("UserProfile", back_populates="feedbacks")
    post = relationship("Post", back_populates="feedbacks")


# --- Folder Suggestions ---


class FolderSuggestion(Base):
    __tablename__ = "folder_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    folder_name = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    post_count = Column(Integer, nullable=False, default=1)
    is_accepted = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
