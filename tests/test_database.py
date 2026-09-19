"""Tests for database operations and deduplication."""

import asyncio
import pytest
from pathlib import Path
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from telegram_ai_filter.database.models import Base, Post, Analysis, Source, UserProfile, Folder
from telegram_ai_filter.database.repositories.post_repository import PostRepository
from telegram_ai_filter.database.repositories.user_repository import UserRepository
from telegram_ai_filter.database.repositories.folder_repository import FolderRepository
from telegram_ai_filter.database.repositories.source_repository import SourceRepository


@pytest.fixture
async def db():
    """Create an in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    await engine.dispose()


@pytest.fixture
def user_repo(db):
    async def _get():
        async with db() as session:
            return UserRepository(session)
    return _get


@pytest.fixture
def post_repo(db):
    async def _get():
        async with db() as session:
            return PostRepository(session)
    return _get


@pytest.fixture
def folder_repo(db):
    async def _get():
        async with db() as session:
            return FolderRepository(session)
    return _get


@pytest.fixture
def source_repo(db):
    async def _get():
        async with db() as session:
            return SourceRepository(session)
    return _get


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_get_or_create_new_user(self, db):
        async with db() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(12345, username="testuser", first_name="Test")

            assert user.telegram_id == 12345
            assert user.username == "testuser"
            assert user.first_name == "Test"

            # System folders should be created
            folder_repo = FolderRepository(session)
            folders = await folder_repo.get_user_folders(user.id)
            assert len(folders) == 2
            names = [f.name for f in folders]
            assert "All Useful" in names
            assert "Saved" in names

    @pytest.mark.asyncio
    async def test_get_or_create_existing_user(self, db):
        async with db() as session:
            repo = UserRepository(session)
            user1 = await repo.get_or_create(12345, username="testuser")
            user2 = await repo.get_or_create(12345, username="updated")
            assert user1.id == user2.id

    @pytest.mark.asyncio
    async def test_update_user(self, db):
        async with db() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(12345)
            updated = await repo.update(user, interests="FPV, AI")
            assert updated.interests == "FPV, AI"


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_is_processed_returns_false_for_new_post(self, db):
        async with db() as session:
            repo = PostRepository(session)
            assert await repo.is_processed(1001, 1) is False

    @pytest.mark.asyncio
    async def test_is_processed_returns_true_after_creating_post(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Test Channel", "testchannel")

            post_repo = PostRepository(session)
            await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Test Channel",
                text="Hello world",
            )

            assert await post_repo.is_processed(1001, 1) is True
            assert await post_repo.is_processed(1001, 2) is False

    @pytest.mark.asyncio
    async def test_get_by_telegram(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Test Channel")

            post_repo = PostRepository(session)
            await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=42,
                channel_name="Test Channel",
                text="Test post",
            )

            post = await post_repo.get_by_telegram(1001, 42)
            assert post is not None
            assert post.text == "Test post"


class TestFolderRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_folder(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            folder_repo = FolderRepository(session)
            folder = await folder_repo.create(user.id, "My Folder", "A test folder")

            assert folder.name == "My Folder"
            assert folder.description == "A test folder"
            assert folder.is_system is False

    @pytest.mark.asyncio
    async def test_get_by_name(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            folder_repo = FolderRepository(session)
            await folder_repo.create(user.id, "Test")

            found = await folder_repo.get_by_name(user.id, "Test")
            assert found is not None
            assert found.name == "Test"

    @pytest.mark.asyncio
    async def test_system_folders_not_deletable(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            folder_repo = FolderRepository(session)
            folders = await folder_repo.get_user_folders(user.id)
            system_folder = next(f for f in folders if f.is_system)

            with pytest.raises(ValueError, match="Cannot delete system folder"):
                await folder_repo.delete(system_folder)

    @pytest.mark.asyncio
    async def test_get_folder_names(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            folder_repo = FolderRepository(session)
            await folder_repo.create(user.id, "Custom1")
            await folder_repo.create(user.id, "Custom2")

            names = await folder_repo.get_folder_names(user.id)
            assert "All Useful" in names
            assert "Saved" in names
            assert "Custom1" in names
            assert "Custom2" in names


class TestSourceRepository:
    @pytest.mark.asyncio
    async def test_add_and_get_source(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Test Channel", "testchannel")

            sources = await source_repo.get_user_sources(user.id)
            assert len(sources) == 1
            assert sources[0].channel_name == "Test Channel"

    @pytest.mark.asyncio
    async def test_get_all_channel_ids(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(12345)

            source_repo = SourceRepository(session)
            await source_repo.add(user.id, 1001, "Channel 1")
            await source_repo.add(user.id, 1002, "Channel 2")

            ids = await source_repo.get_all_channel_ids(user.id)
            assert set(ids) == {1001, 1002}
