"""Main entry point - application orchestration."""

from __future__ import annotations

import asyncio
import html
import logging
import sys
from pathlib import Path

from .ai import OpenAICompatibleProvider
from .config.settings import Settings, load_settings
from .database.engine import Database, init_db
from .database.repositories.post_repository import PostRepository
from .database.repositories.source_repository import SourceRepository
from .database.repositories.user_repository import UserRepository
from .database.repositories.folder_repository import FolderRepository
from .services.analysis_service import AnalysisService
from .services.folder_service import FolderService
from .services.stats_service import StatsService
from .services.user_service import UserService
from .telegram.bot import TelegramBot
from .telegram.channel_reader import ChannelReader

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def setup_logging(level: str) -> None:
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    handler = logging.FileHandler(logs_dir / "app.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        handlers=[handler, console_handler],
    )


class Application:
    """Main application that wires all components together."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db: Database | None = None
        self.bot: TelegramBot | None = None
        self.reader: ChannelReader | None = None
        self.user_service: UserService | None = None
        self.analysis_service: AnalysisService | None = None
        self.folder_service: FolderService | None = None
        self.stats_service: StatsService | None = None

    async def initialize(self) -> None:
        """Initialize all components."""
        db_path = BASE_DIR / "data" / "filter.db"
        self.db = await init_db(db_path)

        # AI provider
        ai_provider = OpenAICompatibleProvider(
            base_url=self.settings.ai_base_url,
            api_key=self.settings.ai_api_key,
            model=self.settings.ai_model,
        )

        # Services
        self.user_service = UserService(self.db.session_factory)
        self.analysis_service = AnalysisService(ai_provider, self.db.session_factory)
        self.folder_service = FolderService(self.db.session_factory)
        self.stats_service = StatsService(self.db.session_factory)

        # Telegram channel reader
        self.reader = ChannelReader(
            api_id=self.settings.api_id,
            api_hash=self.settings.api_hash,
            session_name=self.settings.session_name,
        )

        # Telegram bot
        self.bot = TelegramBot(
            token=self.settings.bot_token,
            target_chat_id=self.settings.target_chat_id,
        )

        logger.info("Application initialized")

    def _register_bot_handlers(self) -> None:
        """Register bot command and callback handlers."""
        if not self.bot or not self.user_service:
            return

        # Override bot handlers with service calls
        self.bot._on_start = self._handle_bot_start
        self.bot._on_help = self._handle_bot_help
        self.bot._on_settings = self._handle_bot_settings
        self.bot._on_folders = self._handle_bot_folders
        self.bot._on_sources = self._handle_bot_sources
        self.bot._on_history = self._handle_bot_history
        self.bot._on_stats = self._handle_bot_stats
        self.bot._on_feedback = self._handle_bot_feedback
        self.bot._on_save_post = self._handle_bot_save
        self.bot._on_move_post = self._handle_bot_move
        self.bot._on_get_folders_for_move = self._handle_bot_get_folders_for_move
        self.bot._on_add_source = self._handle_bot_add_source
        self.bot._on_remove_source = self._handle_bot_remove_source

    async def _handle_bot_start(self, user_id: int) -> str:
        user = await self.user_service.get_or_create_user(user_id)
        return (
            f"Hello, {user.first_name or 'user'}!\n\n"
            "I am your personal AI-powered Telegram post filter.\n\n"
            "I will analyze posts from your channels and show you only the useful ones.\n\n"
            "Use /help to see available commands."
        )

    async def _handle_bot_help(self, user_id: int) -> str:
        return (
            "<b>Available Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/help - Show this help\n"
            "/settings - Manage filter settings\n"
            "/folders - Manage folders\n"
            "/sources - Manage content sources\n"
            "/history - View recent posts\n"
            "/stats - View statistics\n\n"
            "<b>How it works:</b>\n"
            "1. Add Telegram channels as sources\n"
            "2. Set your interests in settings\n"
            "3. I will analyze posts and show useful ones\n"
            "4. Give feedback to improve filtering"
        )

    async def _handle_bot_settings(self, user_id: int) -> dict[str, str]:
        return await self.user_service.get_settings_dict(user_id)

    async def _handle_bot_folders(self, user_id: int) -> list[str]:
        result = await self.folder_service.list_folders(user_id)
        return [result]

    async def _handle_bot_sources(self, user_id: int) -> list[str]:
        async with self.db.session_factory() as session:
            user_repo = UserRepository(session)
            source_repo = SourceRepository(session)
            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                return ["No profile found."]
            names = await source_repo.get_source_names(user.id)
            return [names]

    async def _handle_bot_history(self, user_id: int, offset: int = 0, limit: int = 5) -> list[dict]:
        return await self.analysis_service.get_user_posts(user_id, limit=limit)

    async def _handle_bot_stats(self, user_id: int) -> dict[str, str]:
        stats_text = await self.stats_service.get_user_stats(user_id)
        return {"stats": stats_text}

    async def _handle_bot_feedback(self, user_id: int, post_id: str, feedback_type: str) -> dict:
        from .database.models import FeedbackType
        from .database.repositories.feedback_repository import FeedbackRepository

        async with self.db.session_factory() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                return {"message": "User not found."}

            feedback_repo = FeedbackRepository(session)
            fb_type = FeedbackType.USEFUL if feedback_type == "useful" else FeedbackType.NOT_USEFUL
            await feedback_repo.add(
                user_id=user.id,
                post_id=int(post_id),
                feedback_type=fb_type,
            )
            return {"message": f"Feedback recorded: {feedback_type}"}

    async def _handle_bot_save(self, user_id: int, post_id: str) -> bool:
        result = await self.folder_service.move_post(user_id, int(post_id), "Saved")
        return "moved" in result.lower() or "saved" in result.lower()

    async def _handle_bot_move(self, user_id: int, post_id: str, folder: str) -> bool:
        result = await self.folder_service.move_post(user_id, int(post_id), folder)
        return "moved" in result.lower()

    async def _handle_bot_get_folders_for_move(self, user_id: int) -> list[str]:
        async with self.db.session_factory() as session:
            user_repo = UserRepository(session)
            folder_repo = FolderRepository(session)
            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                return []
            return await folder_repo.get_folder_names(user.id)

    async def _parse_channel_input(self, channel_input: str) -> tuple[int | None, str | None, str]:
        """Parse channel input to extract channel_id, username, and name.
        
        Supports: @username, username, t.me/username, https://t.me/username
        Returns (channel_id, username, display_name).
        channel_id is None if we can't resolve (requires Telethon).
        """
        import re

        channel_input = channel_input.strip()
        
        # Extract username from various formats
        username = None
        
        # Match @username
        m = re.match(r"^@(\w+)$", channel_input)
        if m:
            username = m.group(1)
        else:
            # Match t.me/username or https://t.me/username
            m = re.match(r"(?:https?://)?t\.me/(\w+)$", channel_input)
            if m:
                username = m.group(1)
            else:
                # Match plain username (no @)
                m = re.match(r"^(\w+)$", channel_input)
                if m:
                    username = m.group(1)
        
        if not username:
            return None, None, channel_input
        
        # Generate a deterministic channel_id from username hash for MVP
        # In production, use Telethon client.get_peer_info() to resolve
        channel_id = abs(hash(username)) % (2**31 - 1)
        display_name = username.replace("_", " ").title()
        
        return channel_id, username, display_name

    async def _handle_bot_add_source(self, user_id: int, channel_input: str) -> str:
        """Add a Telegram channel as a source."""
        channel_id, username, display_name = await self._parse_channel_input(channel_input)
        
        if not username:
            return (
                "Invalid channel format.\n\n"
                "Use one of:\n"
                "  @channel_name\n"
                "  channel_name\n"
                "  t.me/channel_name\n"
                "  https://t.me/channel_name"
            )

        async with self.db.session_factory() as session:
            user_repo = UserRepository(session)
            source_repo = SourceRepository(session)

            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                return "No profile found. Send /start first."

            # Check for duplicates
            existing = await source_repo.get_by_channel_id(user.id, channel_id)
            if existing:
                return f"Source <b>{html.escape(display_name)}</b> is already added."

            try:
                await source_repo.add(
                    user_id=user.id,
                    channel_id=channel_id,
                    channel_name=display_name,
                    channel_username=username,
                )
                return f"Source <b>{html.escape(display_name)}</b> (@{username}) added successfully."
            except Exception:
                logger.exception("Failed to add source")
                return "Failed to add source. Please try again."

    async def _handle_bot_remove_source(self, user_id: int, channel_input: str) -> str:
        """Remove a source channel."""
        channel_input_clean = channel_input.strip()

        async with self.db.session_factory() as session:
            user_repo = UserRepository(session)
            source_repo = SourceRepository(session)

            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                return "No profile found. Send /start first."

            sources = await source_repo.get_user_sources(user.id)
            if not sources:
                return "No sources to remove."

            target_source = None

            # Try matching by source_id (numeric)
            if channel_input_clean.isdigit():
                source_id = int(channel_input_clean)
                for s in sources:
                    if s.id == source_id:
                        target_source = s
                        break

            # Try matching by @username or username
            if not target_source:
                clean = channel_input_clean.lstrip("@")
                for s in sources:
                    if s.channel_username and s.channel_username.lower() == clean.lower():
                        target_source = s
                        break

            # Try matching by channel_name
            if not target_source:
                for s in sources:
                    if s.channel_name.lower() == channel_input_clean.lower():
                        target_source = s
                        break

            if not target_source:
                return (
                    "Source not found.\n\n"
                    "Use /sources to see available sources.\n"
                    "You can remove by @username or source ID."
                )

            try:
                await source_repo.deactivate(target_source)
                name = target_source.channel_name
                return f"Source <b>{html.escape(name)}</b> removed successfully."
            except Exception:
                logger.exception("Failed to remove source")
                return "Failed to remove source. Please try again."

    async def _on_new_post(self, post: dict) -> None:
        """Handle a new post from a Telegram channel."""
        user_id = self.settings.target_chat_id

        analysis = await self.analysis_service.analyze_post(
            user_telegram_id=user_id,
            channel_id=post["channel_id"],
            telegram_message_id=post["telegram_message_id"],
            channel_name=post["channel_name"],
            channel_username=post.get("channel_username"),
            text=post.get("text", ""),
            message_url=post.get("message_url"),
            has_photo=post.get("has_photo", False),
            has_video=post.get("has_video", False),
            telegram_created_at=post.get("telegram_created_at"),
        )

        if analysis and analysis.useful:
            # Get the post ID from database
            async with self.db.session_factory() as session:
                post_repo = PostRepository(session)
                db_post = await post_repo.get_by_telegram(
                    post["channel_id"], post["telegram_message_id"]
                )
                if db_post:
                    await self.bot.send_post(
                        chat_id=self.settings.target_chat_id,
                        post_id=str(db_post.id),
                        source=post["channel_name"],
                        category=f"{analysis.category} ({analysis.content_type.value})",
                        score=float(analysis.score),
                        reason=analysis.reason,
                        post_text=post.get("text", "")[:3000],
                        post_url=post.get("message_url"),
                    )

    async def run(self) -> None:
        """Run the application."""
        await self.initialize()
        self._register_bot_handlers()

        logger.info("Starting Telegram AI Filter...")

        # Start the channel reader
        await self.reader.start()
        self.reader.set_channels(self.settings.channels)
        self.reader.register_handler(self._on_new_post)

        # Start the bot
        app = self.bot.create_application()

        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)

            logger.info("Application is running. Press Ctrl+C to stop.")

            # Run both the reader and bot polling concurrently
            reader_task = asyncio.create_task(self.reader.run_until_disconnected())

            # Wait for interrupt
            try:
                await reader_task
            except asyncio.CancelledError:
                pass

        finally:
            logger.info("Shutting down...")
            await self.reader.stop()
            if self.bot:
                await self.bot.stop()
            if self.db:
                await self.db.close()
            logger.info("Application stopped")


def main() -> None:
    """Main entry point."""
    settings = load_settings()

    # Validate required settings
    required = {
        "API_ID": settings.api_id,
        "API_HASH": settings.api_hash,
        "BOT_TOKEN": settings.bot_token,
        "AI_BASE_URL": settings.ai_base_url,
        "AI_MODEL": settings.ai_model,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"Missing required .env values: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    setup_logging(settings.log_level)
    logger.info("Starting Telegram AI Filter v0.1.0")

    app = Application(settings)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.exception("Fatal error")
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
