"""Folder repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Folder


class FolderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, folder_id: int) -> Folder | None:
        result = await self.session.execute(
            select(Folder).where(Folder.id == folder_id)
        )
        return result.scalar_one_or_none()

    async def get_user_folders(self, user_id: int) -> list[Folder]:
        result = await self.session.execute(
            select(Folder)
            .where(Folder.user_id == user_id)
            .order_by(Folder.is_system.desc(), Folder.name)
        )
        return list(result.scalars().all())

    async def get_by_name(self, user_id: int, name: str) -> Folder | None:
        result = await self.session.execute(
            select(Folder).where(
                Folder.user_id == user_id,
                Folder.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        name: str,
        description: str = "",
        is_system: bool = False,
        parent_id: int | None = None,
    ) -> Folder:
        folder = Folder(
            user_id=user_id,
            name=name,
            description=description,
            is_system=is_system,
            parent_id=parent_id,
        )
        self.session.add(folder)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def update(self, folder: Folder, **kwargs) -> Folder:
        for key, value in kwargs.items():
            if hasattr(folder, key):
                setattr(folder, key, value)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def delete(self, folder: Folder) -> None:
        if folder.is_system:
            raise ValueError("Cannot delete system folder")
        await self.session.delete(folder)
        await self.session.commit()

    async def get_folder_names(self, user_id: int) -> list[str]:
        folders = await self.get_user_folders(user_id)
        return [f.name for f in folders]

    async def get_folder_descriptions(self, user_id: int) -> str:
        folders = await self.get_user_folders(user_id)
        lines = []
        for f in folders:
            desc = f" - {f.description}" if f.description else ""
            lines.append(f"{f.name}{desc}")
        return "\n".join(lines) if lines else "No folders"
