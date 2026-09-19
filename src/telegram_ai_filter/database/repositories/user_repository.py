"""User profile repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Folder, UserProfile


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> UserProfile | None:
        result = await self.session.execute(
            select(UserProfile).where(UserProfile.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, telegram_id: int, **kwargs) -> UserProfile:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = UserProfile(telegram_id=telegram_id, **kwargs)
            self.session.add(user)
            await self.session.commit()

            # Create system folders
            for name, description in [
                ("All Useful", "All posts rated as useful"),
                ("Saved", "Posts manually saved by user"),
            ]:
                folder = Folder(
                    user_id=user.id,
                    name=name,
                    description=description,
                    is_system=True,
                )
                self.session.add(folder)
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def update(self, user: UserProfile, **kwargs) -> UserProfile:
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_all(self) -> list[UserProfile]:
        result = await self.session.execute(select(UserProfile))
        return list(result.scalars().all())
