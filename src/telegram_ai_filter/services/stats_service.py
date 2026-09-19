"""Statistics service."""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from ..database.models import Analysis, Feedback, Post, Source
from ..database.repositories.feedback_repository import FeedbackRepository
from ..database.repositories.post_repository import PostRepository
from ..database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class StatsService:
    """Provides user and content statistics."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_user_stats(self, telegram_id: int) -> str:
        """Get formatted statistics for a user."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            post_repo = PostRepository(session)
            feedback_repo = FeedbackRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            counts = await post_repo.get_user_stats(user.id)
            feedback_counts = await feedback_repo.get_user_feedback_count(user.id)

            useful_pct = (
                round(counts["useful"] / counts["total"] * 100)
                if counts["total"]
                else 0
            )

            lines = [
                "<b>Your Statistics</b>",
                "",
                f"<b>Total posts analyzed:</b> {counts['total']}",
                f"<b>Useful posts:</b> {counts['useful']} ({useful_pct}%)",
                "",
                "<b>Feedback given:</b>",
                f"  👍 Useful: {feedback_counts.get('useful', 0)}",
                f"  👎 Not useful: {feedback_counts.get('not_useful', 0)}",
                f"  🔖 Saved: {feedback_counts.get('saved', 0)}",
                f"  📂 Moved: {feedback_counts.get('moved', 0)}",
            ]

            return "\n".join(lines)

    async def get_category_stats(self, telegram_id: int) -> dict[str, int]:
        """Get posts per category for a user."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return {}

            result = await session.execute(
                select(Analysis.category, func.count(Analysis.id))
                .join(Post, Analysis.post_id == Post.id)
                .join(Source, Post.source_id == Source.id)
                .where(Source.user_id == user.id)
                .group_by(Analysis.category)
                .order_by(func.count(Analysis.id).desc())
            )
            return {category: count for category, count in result.all()}

    async def get_source_stats(self, telegram_id: int) -> dict[str, int]:
        """Get posts per source for a user."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return {}

            result = await session.execute(
                select(Source.channel_name, func.count(Post.id))
                .join(Post, Post.source_id == Source.id)
                .where(Source.user_id == user.id)
                .group_by(Source.channel_name)
                .order_by(func.count(Post.id).desc())
            )
            return {name: count for name, count in result.all()}
