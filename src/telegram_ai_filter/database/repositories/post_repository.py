"""Post repository."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Analysis, Post


class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_processed(self, channel_id: int, telegram_message_id: int) -> bool:
        result = await self.session.execute(
            select(Post.id).where(
                Post.channel_id == channel_id,
                Post.telegram_message_id == telegram_message_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_by_telegram(self, channel_id: int, telegram_message_id: int) -> Post | None:
        result = await self.session.execute(
            select(Post).where(
                Post.channel_id == channel_id,
                Post.telegram_message_id == telegram_message_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        source_id: int,
        channel_id: int,
        telegram_message_id: int,
        channel_name: str,
        channel_username: str | None = None,
        text: str | None = None,
        message_url: str | None = None,
        has_photo: bool = False,
        has_video: bool = False,
        telegram_created_at: datetime | None = None,
    ) -> Post:
        post = Post(
            source_id=source_id,
            channel_id=channel_id,
            telegram_message_id=telegram_message_id,
            channel_name=channel_name,
            channel_username=channel_username,
            text=text,
            message_url=message_url,
            has_photo=has_photo,
            has_video=has_video,
            telegram_created_at=telegram_created_at,
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def get_user_posts(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        useful_only: bool = False,
    ) -> list[Post]:
        query = (
            select(Post)
            .join(Post.source)
            .join(Post.analysis)
            .where(Post.source.has(user_id=user_id))
        )
        if useful_only:
            query = query.where(Analysis.useful == True)
        query = query.order_by(Post.fetched_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_stats(self, user_id: int) -> dict[str, int]:
        total = await self.session.execute(
            select(func.count(Post.id))
            .join(Post.source)
            .where(Post.source.has(user_id=user_id))
        )
        useful = await self.session.execute(
            select(func.count(Post.id))
            .join(Post.source)
            .join(Post.analysis)
            .where(Post.source.has(user_id=user_id), Analysis.useful == True)
        )
        return {
            "total": total.scalar() or 0,
            "useful": useful.scalar() or 0,
        }

    async def get_by_folder(self, user_id: int, folder_id: int, limit: int = 50) -> list[Post]:
        result = await self.session.execute(
            select(Post)
            .join(Post.source)
            .where(
                Post.source.has(user_id=user_id),
                Post.folder_id == folder_id,
            )
            .order_by(Post.fetched_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
