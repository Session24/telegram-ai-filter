"""Source (Telegram channel) repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Source


class SourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, source_id: int) -> Source | None:
        result = await self.session.execute(
            select(Source).where(Source.id == source_id)
        )
        return result.scalar_one_or_none()

    async def get_user_sources(self, user_id: int) -> list[Source]:
        result = await self.session.execute(
            select(Source)
            .where(Source.user_id == user_id, Source.is_active == True)
            .order_by(Source.added_at)
        )
        return list(result.scalars().all())

    async def get_by_channel_id(self, user_id: int, channel_id: int) -> Source | None:
        result = await self.session.execute(
            select(Source).where(
                Source.user_id == user_id,
                Source.channel_id == channel_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_channel_ids(self, user_id: int) -> list[int]:
        sources = await self.get_user_sources(user_id)
        return [s.channel_id for s in sources]

    async def add(
        self,
        user_id: int,
        channel_id: int,
        channel_name: str,
        channel_username: str | None = None,
    ) -> Source:
        source = Source(
            user_id=user_id,
            channel_id=channel_id,
            channel_name=channel_name,
            channel_username=channel_username,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def deactivate(self, source: Source) -> Source:
        source.is_active = False
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_source_names(self, user_id: int) -> str:
        sources = await self.get_user_sources(user_id)
        if not sources:
            return "No sources added"
        lines = []
        for s in sources:
            username = f"@{s.channel_username}" if s.channel_username else str(s.channel_id)
            lines.append(f"- {s.channel_name} ({username})")
        return "\n".join(lines)
