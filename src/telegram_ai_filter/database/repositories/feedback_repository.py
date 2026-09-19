"""Feedback repository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Feedback, FeedbackType


class FeedbackRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        user_id: int,
        post_id: int,
        feedback_type: FeedbackType,
        reason: str | None = None,
        target_folder_id: int | None = None,
    ) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            post_id=post_id,
            feedback_type=feedback_type,
            reason=reason,
            target_folder_id=target_folder_id,
        )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def get_for_post(self, user_id: int, post_id: int) -> Feedback | None:
        result = await self.session.execute(
            select(Feedback).where(
                Feedback.user_id == user_id,
                Feedback.post_id == post_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_feedback_count(self, user_id: int) -> dict[str, int]:
        result = await self.session.execute(
            select(Feedback.feedback_type, func.count(Feedback.id))
            .where(Feedback.user_id == user_id)
            .group_by(Feedback.feedback_type)
        )
        counts = {ft.value: 0 for ft in FeedbackType}
        for feedback_type, count in result.all():
            counts[feedback_type.value] = count
        return counts

    async def get_user_feedbacks(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Feedback]:
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
