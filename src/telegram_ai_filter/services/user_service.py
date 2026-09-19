"""User profile management service."""

from __future__ import annotations

import logging

from ..config.prompts import FEEDBACK_REASONS
from ..database.models import UserProfile
from ..database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Manages user profiles, interests, and settings."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> UserProfile:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(
                telegram_id,
                username=username,
                first_name=first_name,
            )
            return user

    async def get_user(self, telegram_id: int) -> UserProfile | None:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            return await repo.get_by_telegram_id(telegram_id)

    async def update_interests(self, telegram_id: int, interests: str) -> str:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found. Send /start first."
            await repo.update(user, interests=interests)
            return f"Interests updated to:\n{interests}"

    async def update_excluded_topics(self, telegram_id: int, excluded: str) -> str:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found. Send /start first."
            await repo.update(user, excluded_topics=excluded)
            return f"Excluded topics updated to:\n{excluded}"

    async def update_min_score(self, telegram_id: int, score: int) -> str:
        if not 0 <= score <= 100:
            return "Score must be between 0 and 100."
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found. Send /start first."
            await repo.update(user, min_ai_score=score)
            return f"Minimum AI score set to {score}."

    async def get_user_summary(self, telegram_id: int) -> str:
        user = await self.get_user(telegram_id)
        if not user:
            return "No profile found. Send /start to create one."

        lines = [
            "<b>Your Profile</b>",
            "",
            f"<b>Interests:</b> {user.interests or 'Not set'}",
            f"<b>Excluded:</b> {user.excluded_topics or 'None'}",
            f"<b>Min Score:</b> {user.min_ai_score}",
            f"<b>Notifications:</b> {'On' if user.notifications_enabled else 'Off'}",
            f"<b>Digest:</b> {'On' if user.digest_enabled else 'Off'}",
        ]

        # Custom AI settings
        if user.ai_base_url:
            lines.append(f"<b>AI URL:</b> {user.ai_base_url}")
        if user.ai_model:
            lines.append(f"<b>AI Model:</b> {user.ai_model}")

        return "\n".join(lines)

    async def get_settings_dict(self, telegram_id: int) -> dict[str, str]:
        user = await self.get_user(telegram_id)
        if not user:
            return {}
        return {
            "Interests": user.interests or "Not set",
            "Excluded Topics": user.excluded_topics or "None",
            "Min Score": str(user.min_ai_score),
            "Notifications": "On" if user.notifications_enabled else "Off",
            "Digest": "On" if user.digest_enabled else "Off",
            "AI Model": user.ai_model or "Default",
        }

    async def toggle_notifications(self, telegram_id: int) -> str:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found."
            new_value = not user.notifications_enabled
            await repo.update(user, notifications_enabled=new_value)
            return f"Notifications {'enabled' if new_value else 'disabled'}."

    async def toggle_digest(self, telegram_id: int) -> str:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found."
            new_value = not user.digest_enabled
            await repo.update(user, digest_enabled=new_value)
            return f"Daily digest {'enabled' if new_value else 'disabled'}."

    async def update_ai_settings(
        self,
        telegram_id: int,
        ai_base_url: str | None = None,
        ai_api_key: str | None = None,
        ai_model: str | None = None,
    ) -> str:
        async with self.session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if not user:
                return "User not found."
            updates = {}
            if ai_base_url is not None:
                updates["ai_base_url"] = ai_base_url
            if ai_api_key is not None:
                updates["ai_api_key"] = ai_api_key
            if ai_model is not None:
                updates["ai_model"] = ai_model
            if updates:
                await repo.update(user, **updates)
            return "AI settings updated."

    @staticmethod
    def get_feedback_reasons() -> dict[str, str]:
        return FEEDBACK_REASONS.copy()
