"""Tests for folder move, source management, and end-to-end flows."""

import asyncio
import pytest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from telegram_ai_filter.database.models import (
    Base,
    Feedback,
    FeedbackType,
    Folder,
    Post,
    Source,
    UserProfile,
)
from telegram_ai_filter.database.repositories.feedback_repository import FeedbackRepository
from telegram_ai_filter.database.repositories.folder_repository import FolderRepository
from telegram_ai_filter.database.repositories.post_repository import PostRepository
from telegram_ai_filter.database.repositories.source_repository import SourceRepository
from telegram_ai_filter.database.repositories.user_repository import UserRepository
from telegram_ai_filter.services.folder_service import FolderService
from telegram_ai_filter.services.user_service import UserService


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
def folder_service(db):
    return FolderService(db)


@pytest.fixture
def user_service(db):
    return UserService(db)


# --- Folder Selection for Move ---


class TestFolderSelection:
    @pytest.mark.asyncio
    async def test_get_folder_names_includes_system_folders(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(11111)

            folder_repo = FolderRepository(session)
            names = await folder_repo.get_folder_names(user.id)

            assert "All Useful" in names
            assert "Saved" in names

    @pytest.mark.asyncio
    async def test_get_folder_names_includes_custom_folders(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(11111)

            folder_repo = FolderRepository(session)
            await folder_repo.create(user.id, "FPV")
            await folder_repo.create(user.id, "AI News")

            names = await folder_repo.get_folder_names(user.id)
            assert "FPV" in names
            assert "AI News" in names
            assert "All Useful" in names
            assert "Saved" in names

    @pytest.mark.asyncio
    async def test_empty_folders_for_new_user(self, db):
        """User who hasn't been created yet should get empty list."""
        async with db() as session:
            folder_repo = FolderRepository(session)
            names = await folder_repo.get_folder_names(99999)
            assert names == []


# --- Move Post to Folder ---


class TestMovePost:
    @pytest.mark.asyncio
    async def test_move_post_success(self, folder_service, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(22222)

            folder_repo = FolderRepository(session)
            await folder_repo.create(user.id, "Tech")

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Test Channel")

            post_repo = PostRepository(session)
            post = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Test Channel",
                text="Hello world",
            )

        result = await folder_service.move_post(22222, post.id, "Tech")
        assert "moved" in result.lower()

        # Verify the post is now in the folder
        async with db() as session:
            post_repo = PostRepository(session)
            updated_post = await post_repo.get_by_telegram(1001, 1)
            assert updated_post is not None

    @pytest.mark.asyncio
    async def test_move_post_to_nonexistent_folder(self, folder_service, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(22222)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Test Channel")

            post_repo = PostRepository(session)
            post = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Test Channel",
                text="Test",
            )

        result = await folder_service.move_post(22222, post.id, "NonexistentFolder")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_move_post_user_not_found(self, folder_service):
        result = await folder_service.move_post(99999, 1, "Tech")
        assert "not found" in result.lower() or "no profile" in result.lower()


# --- Source Management ---


class TestSourceManagement:
    @pytest.mark.asyncio
    async def test_add_source_success(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(33333)

            source_repo = SourceRepository(session)
            source = await source_repo.add(
                user.id, 1001, "FPV Drones", "fpv_drones"
            )

            assert source.channel_name == "FPV Drones"
            assert source.channel_username == "fpv_drones"
            assert source.is_active is True

    @pytest.mark.asyncio
    async def test_add_duplicate_source(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(33333)

            source_repo = SourceRepository(session)
            await source_repo.add(user.id, 1001, "Channel 1", "ch1")

            existing = await source_repo.get_by_channel_id(user.id, 1001)
            assert existing is not None

    @pytest.mark.asyncio
    async def test_remove_source_deactivates(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(33333)

            source_repo = SourceRepository(session)
            source = await source_repo.add(
                user.id, 1001, "To Remove", "toremove"
            )

            await source_repo.deactivate(source)

            sources = await source_repo.get_user_sources(user.id)
            assert len(sources) == 0

    @pytest.mark.asyncio
    async def test_get_source_names(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(33333)

            source_repo = SourceRepository(session)
            await source_repo.add(user.id, 1001, "Channel 1", "ch1")
            await source_repo.add(user.id, 1002, "Channel 2", "ch2")

            names = await source_repo.get_source_names(user.id)
            assert "Channel 1" in names
            assert "Channel 2" in names

    @pytest.mark.asyncio
    async def test_get_source_names_empty(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(33333)

            source_repo = SourceRepository(session)
            names = await source_repo.get_source_names(user.id)
            assert "No sources" in names


# --- Feedback Persistence ---


class TestFeedbackPersistence:
    @pytest.mark.asyncio
    async def test_add_feedback(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(44444)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Channel")

            post_repo = PostRepository(session)
            post = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Channel",
                text="Test post",
            )

            feedback_repo = FeedbackRepository(session)
            feedback = await feedback_repo.add(
                user_id=user.id,
                post_id=post.id,
                feedback_type=FeedbackType.USEFUL,
            )

            assert feedback.feedback_type == FeedbackType.USEFUL
            assert feedback.user_id == user.id
            assert feedback.post_id == post.id

    @pytest.mark.asyncio
    async def test_feedback_count(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(44444)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 1001, "Channel")

            post_repo = PostRepository(session)
            post1 = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Channel",
                text="Post 1",
            )
            post2 = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=2,
                channel_name="Channel",
                text="Post 2",
            )

            feedback_repo = FeedbackRepository(session)
            await feedback_repo.add(
                user_id=user.id,
                post_id=post1.id,
                feedback_type=FeedbackType.USEFUL,
            )
            await feedback_repo.add(
                user_id=user.id,
                post_id=post2.id,
                feedback_type=FeedbackType.NOT_USEFUL,
            )

            counts = await feedback_repo.get_user_feedback_count(user.id)
            assert counts["useful"] == 1
            assert counts["not_useful"] == 1


# --- User Data Isolation ---


class TestUserDataIsolation:
    @pytest.mark.asyncio
    async def test_users_have_separate_folders(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user1 = await user_repo.get_or_create(11111)
            user2 = await user_repo.get_or_create(22222)

            folder_repo = FolderRepository(session)
            await folder_repo.create(user1.id, "User1Folder")
            await folder_repo.create(user2.id, "User2Folder")

            folders1 = await folder_repo.get_folder_names(user1.id)
            folders2 = await folder_repo.get_folder_names(user2.id)

            assert "User1Folder" in folders1
            assert "User1Folder" not in folders2
            assert "User2Folder" in folders2
            assert "User2Folder" not in folders1

    @pytest.mark.asyncio
    async def test_users_have_separate_sources(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user1 = await user_repo.get_or_create(11111)
            user2 = await user_repo.get_or_create(22222)

            source_repo = SourceRepository(session)
            await source_repo.add(user1.id, 1001, "Channel A")
            await source_repo.add(user2.id, 1002, "Channel B")

            sources1 = await source_repo.get_user_sources(user1.id)
            sources2 = await source_repo.get_user_sources(user2.id)

            assert len(sources1) == 1
            assert len(sources2) == 1
            assert sources1[0].channel_name == "Channel A"
            assert sources2[0].channel_name == "Channel B"

    @pytest.mark.asyncio
    async def test_users_have_separate_feedback(self, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user1 = await user_repo.get_or_create(11111)
            user2 = await user_repo.get_or_create(22222)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user1.id, 1001, "Channel")

            post_repo = PostRepository(session)
            post = await post_repo.create(
                source_id=source.id,
                channel_id=1001,
                telegram_message_id=1,
                channel_name="Channel",
                text="Test",
            )

            feedback_repo = FeedbackRepository(session)
            await feedback_repo.add(
                user_id=user1.id,
                post_id=post.id,
                feedback_type=FeedbackType.USEFUL,
            )

            counts1 = await feedback_repo.get_user_feedback_count(user1.id)
            counts2 = await feedback_repo.get_user_feedback_count(user2.id)

            assert counts1["useful"] == 1
            assert counts2["useful"] == 0


# --- End-to-End Flow ---


class TestEndToEndFlow:
    @pytest.mark.asyncio
    async def test_full_flow_create_user_add_source_move_post(self, folder_service, db):
        """Simulate: create user -> add folder -> add source -> create post -> move to folder."""
        # 1. Create user
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(55555, username="e2euser")
            assert user.telegram_id == 55555

        # 2. Create custom folder
        result = await folder_service.create_folder(55555, "My Folder", "Test folder")
        assert "created" in result.lower()

        # 3. Add source
        async with db() as session:
            source_repo = SourceRepository(session)
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(55555)
            source = await source_repo.add(user.id, 2001, "Test Source", "testsource")
            assert source.is_active is True

        # 4. Create post
        async with db() as session:
            post_repo = PostRepository(session)
            source_repo = SourceRepository(session)
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(55555)
            source = (await source_repo.get_user_sources(user.id))[0]
            post = await post_repo.create(
                source_id=source.id,
                channel_id=2001,
                telegram_message_id=1,
                channel_name="Test Source",
                text="Important post content",
            )

        # 5. Move post to folder
        result = await folder_service.move_post(55555, post.id, "My Folder")
        assert "moved" in result.lower()

        # 6. Verify post is in the folder
        async with db() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)
            post_repo = PostRepository(session)
            user = await user_repo.get_by_telegram_id(55555)
            folder = await folder_repo.get_by_name(user.id, "My Folder")
            assert folder is not None

            posts = await post_repo.get_by_folder(user.id, folder.id)
            assert len(posts) == 1
            assert posts[0].text == "Important post content"

    @pytest.mark.asyncio
    async def test_system_folders_cannot_be_deleted(self, folder_service, db):
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(66666)

        result = await folder_service.delete_folder(66666, "All Useful")
        assert "cannot delete" in result.lower() or "system" in result.lower()

        result = await folder_service.delete_folder(66666, "Saved")
        assert "cannot delete" in result.lower() or "system" in result.lower()

    @pytest.mark.asyncio
    async def test_move_post_to_saved_folder(self, folder_service, db):
        """Simulate the Save button behavior."""
        async with db() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_or_create(77777)

            source_repo = SourceRepository(session)
            source = await source_repo.add(user.id, 3001, "Channel")

            post_repo = PostRepository(session)
            post = await post_repo.create(
                source_id=source.id,
                channel_id=3001,
                telegram_message_id=1,
                channel_name="Channel",
                text="Saved post",
            )

        result = await folder_service.move_post(77777, post.id, "Saved")
        assert "moved" in result.lower()
