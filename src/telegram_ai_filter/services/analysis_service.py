"""Post analysis service - core business logic."""

from __future__ import annotations

import logging

from ..ai.provider import AIProvider, AIProviderError
from ..ai.schemas import PostAnalysis
from ..config.prompts import build_system_prompt
from ..database.models import Analysis, ContentType, Folder, ImportanceLevel, Post
from ..database.repositories.folder_repository import FolderRepository
from ..database.repositories.post_repository import PostRepository
from ..database.repositories.source_repository import SourceRepository
from ..database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrates post analysis: receives post -> AI analysis -> store result -> route."""

    def __init__(self, ai_provider: AIProvider, session_factory):
        self.ai = ai_provider
        self.session_factory = session_factory

    async def analyze_post(
        self,
        user_telegram_id: int,
        channel_id: int,
        telegram_message_id: int,
        channel_name: str,
        channel_username: str | None,
        text: str,
        message_url: str | None = None,
        has_photo: bool = False,
        has_video: bool = False,
        telegram_created_at=None,
        source_id: int | None = None,
    ) -> PostAnalysis | None:
        """Analyze a post and store the result. Returns None if already processed."""
        async with self.session_factory() as session:
            post_repo = PostRepository(session)
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)

            # Deduplication check
            if await post_repo.is_processed(channel_id, telegram_message_id):
                logger.debug("Post already processed: %s:%s", channel_id, telegram_message_id)
                return None

            # Get user
            user = await user_repo.get_by_telegram_id(user_telegram_id)
            if not user:
                logger.warning("User %s not found", user_telegram_id)
                return None

            # Get or resolve source
            if not source_id:
                source_repo = SourceRepository(session)
                source = await source_repo.get_by_channel_id(user.id, channel_id)
                if not source:
                    source = await source_repo.add(
                        user_id=user.id,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        channel_username=channel_username,
                    )
                source_id = source.id

            # Create post record
            post = await post_repo.create(
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

            # Build system prompt with user context
            folders_desc = await folder_repo.get_folder_descriptions(user.id)
            system_prompt = build_system_prompt(
                interests=user.interests,
                excluded_topics=user.excluded_topics,
                folders=folders_desc,
            )

            # AI analysis
            try:
                analysis = await self.ai.analyze_post(text, system_prompt)
            except AIProviderError as exc:
                logger.error("AI analysis failed for post %s:%s: %s", channel_id, telegram_message_id, exc)
                return None

            # Store analysis
            analysis_record = Analysis(
                post_id=post.id,
                useful=analysis.useful,
                score=analysis.score,
                category=analysis.category,
                subcategory=analysis.subcategory,
                content_type=ContentType(analysis.content_type.value),
                importance=ImportanceLevel(analysis.importance.value),
                reason=analysis.reason,
                suggested_folder=analysis.suggested_folder,
            )
            session.add(analysis_record)

            # Route to folder
            if analysis.useful and analysis.suggested_folder:
                folder = await folder_repo.get_by_name(user.id, analysis.suggested_folder)
                if folder:
                    post.folder_id = folder.id

            await session.commit()
            logger.info(
                "Analyzed post %s:%s - useful=%s score=%d category=%s",
                channel_id,
                telegram_message_id,
                analysis.useful,
                analysis.score,
                analysis.category,
            )

            return analysis

    async def get_post_analysis(self, post_id: int) -> dict | None:
        """Get analysis result for a post."""
        async with self.session_factory() as session:
            post_repo = PostRepository(session)
            from sqlalchemy import select
            from ..database.models import Post, Analysis

            result = await session.execute(
                select(Post, Analysis)
                .join(Analysis, Analysis.post_id == Post.id)
                .where(Post.id == post_id)
            )
            row = result.first()
            if not row:
                return None

            post, analysis = row
            return {
                "post_id": post.id,
                "channel_name": post.channel_name,
                "text": post.text,
                "message_url": post.message_url,
                "useful": analysis.useful,
                "score": analysis.score,
                "category": analysis.category,
                "subcategory": analysis.subcategory,
                "content_type": analysis.content_type.value,
                "importance": analysis.importance.value,
                "reason": analysis.reason,
                "suggested_folder": analysis.suggested_folder,
            }

    async def get_user_posts(
        self, telegram_id: int, limit: int = 20, useful_only: bool = False
    ) -> list[dict]:
        """Get user's posts with analysis."""
        async with self.session_factory() as session:
            user_repo = UserRepository(session)
            post_repo = PostRepository(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return []

            from sqlalchemy import select
            from ..database.models import Post, Analysis

            query = (
                select(Post, Analysis)
                .join(Analysis, Analysis.post_id == Post.id)
                .join(Post.source)
                .where(Post.source.has(user_id=user.id))
            )
            if useful_only:
                query = query.where(Analysis.useful == True)
            query = query.order_by(Post.fetched_at.desc()).limit(limit)

            result = await session.execute(query)
            posts = []
            for post, analysis in result.all():
                posts.append({
                    "id": post.id,
                    "channel_name": post.channel_name,
                    "text": (post.text or "")[:200],
                    "score": analysis.score,
                    "category": analysis.category,
                    "useful": analysis.useful,
                    "importance": analysis.importance.value,
                    "folder_id": post.folder_id,
                })
            return posts
