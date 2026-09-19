"""Application settings loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _parse_channels(value: str) -> list[str]:
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    # Telegram user client (Telethon)
    api_id: int
    api_hash: str
    session_name: str

    # Telegram bot (python-telegram-bot)
    bot_token: str
    target_chat_id: int

    # AI provider
    ai_base_url: str
    ai_api_key: str
    ai_model: str

    # Filter settings
    min_ai_score: int = 70
    channels: list[str] = field(default_factory=list)

    # Logging
    log_level: str = "INFO"


def load_ai_settings() -> Settings:
    """Load only AI-related settings. Telegram fields are left as defaults."""
    min_ai_score = int(os.getenv("MIN_AI_SCORE", "70"))
    if min_ai_score < 0 or min_ai_score > 100:
        raise RuntimeError("MIN_AI_SCORE must be between 0 and 100")

    return Settings(
        api_id=0,
        api_hash="",
        session_name="",
        bot_token="",
        target_chat_id=0,
        ai_base_url=os.getenv("AI_BASE_URL", "").rstrip("/"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", ""),
        min_ai_score=min_ai_score,
        channels=[],
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def load_settings() -> Settings:
    """Load all settings from environment variables."""
    try:
        api_id = int(os.getenv("API_ID", "0"))
        target_chat_id = int(os.getenv("TARGET_CHAT_ID", "0"))
        min_ai_score = int(os.getenv("MIN_AI_SCORE", "70"))
    except ValueError as exc:
        raise RuntimeError("API_ID, TARGET_CHAT_ID and MIN_AI_SCORE must be integers") from exc

    if min_ai_score < 0 or min_ai_score > 100:
        raise RuntimeError("MIN_AI_SCORE must be between 0 and 100")

    return Settings(
        api_id=api_id,
        api_hash=os.getenv("API_HASH", ""),
        session_name=str(BASE_DIR / "data" / "user_session"),
        bot_token=os.getenv("BOT_TOKEN", ""),
        target_chat_id=target_chat_id,
        ai_base_url=os.getenv("AI_BASE_URL", "").rstrip("/"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", ""),
        min_ai_score=min_ai_score,
        channels=_parse_channels(os.getenv("CHANNELS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
