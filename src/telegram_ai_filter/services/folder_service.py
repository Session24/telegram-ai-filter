"""Folder management service."""

from __future__ import annotations

import logging

from sqlalchemy import select, update

from ..database.models import Post
from ..database.repositories.folder_repository import FolderRepository
from ..database.repositories.post_repository import PostRepository
from ..database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class FolderService:
    """Manages user folders for organizing posts."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def list_folders(self, telegram_id: int) -> str:
        """Get formatted list of user folders."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folders = await folder_repo.get_user_folders(user.id)
            if not folders:
                return "<i>No folders found.</i>"

            lines = ["<b>Your Folders</b>", ""]
            for folder in folders:
                tag = " <i>(system)</i>" if folder.is_system else ""
                desc = f"\n  <i>{folder.description}</i>" if folder.description else ""
                lines.append(f"• <b>{folder.name}</b>{tag}{desc}")

            return "\n".join(lines)

    async def create_folder(self, telegram_id: int, name: str, description: str = "") -> str:
        """Create a new folder."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            existing = await folder_repo.get_by_name(user.id, name)
            if existing:
                return f"A folder named <b>{name}</b> already exists."

            await folder_repo.create(user.id, name, description=description)
            logger.info("Folder '%s' created for user %s", name, telegram_id)
            return f"Folder <b>{name}</b> created."

    async def delete_folder(self, telegram_id: int, name: str) -> str:
        """Delete a non-system folder."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folder = await folder_repo.get_by_name(user.id, name)
            if not folder:
                return f"Folder <b>{name}</b> not found."

            if folder.is_system:
                return f"Cannot delete system folder <b>{name}</b>."

            await folder_repo.delete(folder)
            logger.info("Folder '%s' deleted for user %s", name, telegram_id)
            return f"Folder <b>{name}</b> deleted."

    async def rename_folder(self, telegram_id: int, old_name: str, new_name: str) -> str:
        """Rename a folder."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folder = await folder_repo.get_by_name(user.id, old_name)
            if not folder:
                return f"Folder <b>{old_name}</b> not found."

            if folder.is_system:
                return f"Cannot rename system folder <b>{old_name}</b>."

            conflict = await folder_repo.get_by_name(user.id, new_name)
            if conflict:
                return f"A folder named <b>{new_name}</b> already exists."

            await folder_repo.update(folder, name=new_name)
            logger.info("Folder '%s' renamed to '%s' for user %s", old_name, new_name, telegram_id)
            return f"Folder <b>{old_name}</b> renamed to <b>{new_name}</b>."

    async def update_description(self, telegram_id: int, name: str, description: str) -> str:
        """Update folder description."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folder = await folder_repo.get_by_name(user.id, name)
            if not folder:
                return f"Folder <b>{name}</b> not found."

            await folder_repo.update(folder, description=description)
            return f"Description of <b>{name}</b> updated."

    async def move_post(self, telegram_id: int, post_id: int, folder_name: str) -> str:
        """Move a post to a folder."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)
            post_repo = PostRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folder = await folder_repo.get_by_name(user.id, folder_name)
            if not folder:
                return f"Folder <b>{folder_name}</b> not found."

            result = await session.execute(
                select(Post)
                .join(Post.source)
                .where(Post.id == post_id, Post.source.has(user_id=user.id))
            )
            post = result.scalar_one_or_none()
            if not post:
                return f"Post #{post_id} not found."

            await session.execute(
                update(Post.__table__)
                .where(Post.__table__.c.id == post_id)
                .values(folder_id=folder.id)
            )
            await session.commit()
            logger.info("Post %s moved to folder '%s' for user %s", post_id, folder_name, telegram_id)
            return f"Post #{post_id} moved to <b>{folder_name}</b>."

    async def view_folder(self, telegram_id: int, folder_name: str) -> str:
        """View posts in a folder."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)
            post_repo = PostRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            folder = await folder_repo.get_by_name(user.id, folder_name)
            if not folder:
                return f"Folder <b>{folder_name}</b> not found."

            posts = await post_repo.get_by_folder(user.id, folder.id)
            if not posts:
                return f"<b>{folder_name}</b>: <i>No posts in this folder.</i>"

            lines = [f"<b>{folder_name}</b> ({len(posts)} posts)", ""]
            for post in posts:
                preview = (post.text or "")[:100].replace("\n", " ")
                url_part = f" — <a href=\"{post.message_url}\">link</a>" if post.message_url else ""
                lines.append(f"• <b>#{post.id}</b> {preview}…{url_part}")

            return "\n".join(lines)

    async def handle_suggested_folder(self, telegram_id: int, folder_name: str) -> str:
        """Handle AI-suggested new folder — create it if it doesn't exist."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "No profile found. Send /start first."

            existing = await folder_repo.get_by_name(user.id, folder_name)
            if existing:
                return f"Folder <b>{folder_name}</b> already exists."

            await folder_repo.create(user.id, folder_name, description="Created from AI suggestion")
            logger.info("AI-suggested folder '%s' created for user %s", folder_name, telegram_id)
            return f"New folder <b>{folder_name}</b> created from AI suggestion."
