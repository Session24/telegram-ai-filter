"""Telegram bot UI layer for AI-powered content filter."""

from __future__ import annotations

import html
import logging
from typing import Any, Callable, Coroutine

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

PostData = dict[str, Any]
SettingsData = dict[str, Any]
FeedbackResult = dict[str, Any]


class TelegramBot:
    """Pure UI layer Telegram bot that delegates business logic via callbacks."""

    def __init__(
        self,
        token: str,
        target_chat_id: int,
        admin_chat_id: int | None = None,
        on_start: Callable[[int], Coroutine[Any, Any, str]] | None = None,
        on_help: Callable[[int], Coroutine[Any, Any, str]] | None = None,
        on_settings: Callable[[int], Coroutine[Any, Any, SettingsData]] | None = None,
        on_folders: Callable[[int], Coroutine[Any, Any, list[str]]] | None = None,
        on_sources: Callable[[int], Coroutine[Any, Any, list[str]]] | None = None,
        on_history: Callable[[int, int, int], Coroutine[Any, Any, list[PostData]]] | None = None,
        on_stats: Callable[[int], Coroutine[Any, Any, dict[str, Any]]] | None = None,
        on_feedback: Callable[[int, str, str], Coroutine[Any, Any, FeedbackResult]] | None = None,
        on_save_post: Callable[[int, str], Coroutine[Any, Any, bool]] | None = None,
        on_move_post: Callable[[int, str, str], Coroutine[Any, Any, bool]] | None = None,
        on_get_folders_for_move: Callable[[int], Coroutine[Any, Any, list[str]]] | None = None,
        on_folder_set: Callable[[int, str], Coroutine[Any, Any, str]] | None = None,
        on_add_source: Callable[[int, str], Coroutine[Any, Any, str]] | None = None,
        on_remove_source: Callable[[int, str], Coroutine[Any, Any, str]] | None = None,
        on_source_toggle: Callable[[int, str], Coroutine[Any, Any, str]] | None = None,
        on_settings_toggle: Callable[[int, str, str], Coroutine[Any, Any, str]] | None = None,
    ):
        self.token = token
        self.target_chat_id = target_chat_id
        self.admin_chat_id = admin_chat_id
        self._on_start = on_start
        self._on_help = on_help
        self._on_settings = on_settings
        self._on_folders = on_folders
        self._on_sources = on_sources
        self._on_history = on_history
        self._on_stats = on_stats
        self._on_feedback = on_feedback
        self._on_save_post = on_save_post
        self._on_move_post = on_move_post
        self._on_get_folders_for_move = on_get_folders_for_move
        self._on_folder_set = on_folder_set
        self._on_add_source = on_add_source
        self._on_remove_source = on_remove_source
        self._on_source_toggle = on_source_toggle
        self._on_settings_toggle = on_settings_toggle
        self._app: Application | None = None

    @property
    def application(self) -> Application:
        if self._app is None:
            raise RuntimeError("Bot not started yet. Call create_application() first.")
        return self._app

    def create_application(self) -> Application:
        self._app = Application.builder().token(self.token).build()
        self._register_handlers()
        return self._app

    def _register_handlers(self) -> None:
        app = self.application
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_help))
        app.add_handler(CommandHandler("settings", self._handle_settings))
        app.add_handler(CommandHandler("folders", self._handle_folders))
        app.add_handler(CommandHandler("sources", self._handle_sources))
        app.add_handler(CommandHandler("addsource", self._handle_addsource))
        app.add_handler(CommandHandler("removesource", self._handle_removesource))
        app.add_handler(CommandHandler("history", self._handle_history))
        app.add_handler(CommandHandler("stats", self._handle_stats))
        app.add_handler(CallbackQueryHandler(self._handle_callback))

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_start:
                message = await self._on_start(user_id)
            else:
                message = (
                    "Welcome to AI Content Filter Bot!\n\n"
                    "This bot helps filter and organize Telegram content using AI.\n\n"
                    "Use /help to see available commands."
                )
        except Exception:
            logger.exception("Error in on_start callback")
            message = "An error occurred. Please try again later."

        await update.message.reply_text(message, parse_mode="HTML")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_help:
                message = await self._on_help(user_id)
            else:
                message = (
                    "<b>Available Commands:</b>\n\n"
                    "/start - Start the bot\n"
                    "/help - Show this help message\n"
                    "/settings - Manage filter settings\n"
                    "/folders - View and manage folders\n"
                    "/sources - List content sources\n"
                    "/addsource @channel - Add a Telegram channel\n"
                    "/removesource @channel - Remove a source\n"
                    "/history - View recent filtered posts\n"
                    "/stats - View filtering statistics"
                )
        except Exception:
            logger.exception("Error in on_help callback")
            message = "An error occurred. Please try again later."

        await update.message.reply_text(message, parse_mode="HTML")

    async def _handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_settings:
                settings = await self._on_settings(user_id)
                text = self._format_settings(settings)
                keyboard = self._build_settings_keyboard(settings)
                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard if keyboard else None,
                )
            else:
                await update.message.reply_text(
                    "Settings not configured yet.", parse_mode="HTML"
                )
        except Exception:
            logger.exception("Error in on_settings callback")
            await update.message.reply_text(
                "An error occurred loading settings.", parse_mode="HTML"
            )

    async def _handle_folders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_folders:
                folders = await self._on_folders(user_id)
                if not folders:
                    text = "No folders configured yet."
                else:
                    text = "<b>Your Folders:</b>\n\n"
                    for i, folder in enumerate(folders, 1):
                        text += f"{i}. {html.escape(folder)}\n"
            else:
                text = "Folder management not configured yet."
        except Exception:
            logger.exception("Error in on_folders callback")
            text = "An error occurred loading folders."

        await update.message.reply_text(text, parse_mode="HTML")

    async def _handle_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_sources:
                sources = await self._on_sources(user_id)
                if not sources:
                    text = "No sources configured yet."
                else:
                    text = "<b>Content Sources:</b>\n\n"
                    for i, source in enumerate(sources, 1):
                        text += f"{i}. {html.escape(source)}\n"
            else:
                text = "Source management not configured yet."
        except Exception:
            logger.exception("Error in on_sources callback")
            text = "An error occurred loading sources."

        await update.message.reply_text(text, parse_mode="HTML")

    async def _handle_addsource(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /addsource command. Usage: /addsource @channel or t.me/channel."""
        if update.effective_user is None or update.message is None:
            return

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /addsource @channel or /addsource t.me/channel_name\n"
                "Examples:\n"
                "  /addsource @fpv_drones\n"
                "  /addsource https://t.me/fpv_drones",
                parse_mode="HTML",
            )
            return

        channel_input = " ".join(args)
        await self._process_addsource(update, context, channel_input)

    async def _handle_removesource(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /removesource command. Usage: /removesource @channel or source_id."""
        if update.effective_user is None or update.message is None:
            return

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /removesource @channel or /removesource source_id\n"
                "Use /sources to see available sources.",
                parse_mode="HTML",
            )
            return

        channel_input = " ".join(args)
        await self._process_removesource(update, context, channel_input)

    async def _handle_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_history:
                posts = await self._on_history(user_id, 0, 5)
                if not posts:
                    text = "No recent posts in history."
                else:
                    text = "<b>Recent Filtered Posts:</b>\n\n"
                    for post in posts:
                        text += self._format_history_entry(post) + "\n\n"
            else:
                text = "History not available yet."
        except Exception:
            logger.exception("Error in on_history callback")
            text = "An error occurred loading history."

        await update.message.reply_text(text, parse_mode="HTML")

    async def _handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        try:
            if self._on_stats:
                stats = await self._on_stats(user_id)
                text = self._format_stats(stats)
            else:
                text = "Statistics not available yet."
        except Exception:
            logger.exception("Error in on_stats callback")
            text = "An error occurred loading statistics."

        await update.message.reply_text(text, parse_mode="HTML")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.data is None or query.from_user is None:
            return

        await query.answer()
        data = query.data
        user_id = query.from_user.id

        if data.startswith("feedback_"):
            await self._process_feedback(query, user_id, data)
        elif data.startswith("save_"):
            await self._process_save(query, user_id, data)
        elif data.startswith("moveto_"):
            await self._process_move_to_folder(query, user_id, data)
        elif data.startswith("cancel_move_"):
            await query.edit_message_text("Move cancelled.")
        elif data.startswith("move_"):
            await self._process_move(query, user_id, data)
        elif data.startswith("settings_"):
            await self._process_settings_toggle(query, user_id, data)
        elif data.startswith("folder_"):
            await self._process_folder_select(query, user_id, data)
        elif data.startswith("source_"):
            await self._process_source_toggle(query, user_id, data)
        else:
            logger.warning("Unknown callback data: %s", data)

    async def _process_feedback(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process feedback callback: feedback_{post_id}_{type}."""
        parts = data.split("_", 2)
        if len(parts) != 3:
            await query.edit_message_text("Invalid feedback format.")
            return

        post_id = parts[1]
        feedback_type = parts[2]

        if feedback_type not in ("useful", "not_useful"):
            await query.edit_message_text("Invalid feedback type.")
            return

        try:
            if self._on_feedback:
                result = await self._on_feedback(user_id, post_id, feedback_type)
                text = result.get("message", f"Feedback recorded: {feedback_type}")
            else:
                text = f"Feedback recorded: {feedback_type}"
        except Exception:
            logger.exception("Error processing feedback")
            text = "Error recording feedback."

        await query.edit_message_text(text, parse_mode="HTML")

    async def _process_save(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process save callback: save_{post_id}."""
        parts = data.split("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid save format.")
            return

        post_id = parts[1]

        try:
            if self._on_save_post:
                success = await self._on_save_post(user_id, post_id)
                text = "Post saved successfully." if success else "Failed to save post."
            else:
                text = "Save functionality not configured."
        except Exception:
            logger.exception("Error saving post")
            text = "Error saving post."

        await query.edit_message_text(text, parse_mode="HTML")

    async def _process_move(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process move callback: move_{post_id}.
        Shows folder selection keyboard."""
        parts = data.split("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid move format.")
            return

        post_id = parts[1]

        try:
            if self._on_get_folders_for_move:
                folders = await self._on_get_folders_for_move(user_id)
                if not folders:
                    await query.edit_message_text("No folders available. Create one first with /folders.")
                    return

                buttons = []
                for folder_name in folders:
                    buttons.append([
                        InlineKeyboardButton(
                            text=html.escape(folder_name),
                            callback_data=f"moveto_{post_id}_{folder_name}",
                        )
                    ])
                buttons.append([
                    InlineKeyboardButton(text="Cancel", callback_data=f"cancel_move_{post_id}")
                ])
                keyboard = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(
                    "<b>Select a folder:</b>",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await query.edit_message_text("Move functionality not configured.")
        except Exception:
            logger.exception("Error showing folder selection")
            await query.edit_message_text("Error loading folders.")

    async def _process_move_to_folder(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process move to folder: moveto_{post_id}_{folder_name}."""
        parts = data.split("_", 2)
        if len(parts) != 3:
            await query.edit_message_text("Invalid move format.")
            return

        post_id = parts[1]
        folder_name = parts[2]

        try:
            if self._on_move_post:
                success = await self._on_move_post(user_id, post_id, folder_name)
                if success:
                    await query.edit_message_text(
                        f"Post moved to <b>{html.escape(folder_name)}</b>.",
                        parse_mode="HTML",
                    )
                else:
                    await query.edit_message_text("Failed to move post.")
            else:
                await query.edit_message_text("Move functionality not configured.")
        except Exception:
            logger.exception("Error moving post to folder")
            await query.edit_message_text("Error moving post.")

    async def _process_settings_toggle(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process settings toggle: settings_{setting_name}."""
        parts = data.split("_", 2)
        if len(parts) != 2:
            await query.edit_message_text("Invalid settings format.")
            return

        setting_name = parts[1]

        try:
            if self._on_settings_toggle:
                result = await self._on_settings_toggle(user_id, setting_name, "")
                text = result if result else "Setting updated."
            else:
                text = "Settings toggle not configured."
        except Exception:
            logger.exception("Error toggling setting")
            text = "Error updating setting."

        await query.edit_message_text(text, parse_mode="HTML")

    async def _process_folder_select(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process folder selection: folder_{folder_name}."""
        parts = data.split("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid folder format.")
            return

        folder_name = parts[1]

        try:
            if self._on_folder_set:
                result = await self._on_folder_set(user_id, folder_name)
                text = result if result else f"Folder set to: {html.escape(folder_name)}"
            else:
                text = "Folder selection not configured."
        except Exception:
            logger.exception("Error selecting folder")
            text = "Error selecting folder."

        await query.edit_message_text(text, parse_mode="HTML")

    async def _process_source_toggle(
        self, query: Any, user_id: int, data: str
    ) -> None:
        """Process source toggle: source_{source_name}."""
        parts = data.split("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid source format.")
            return

        source_name = parts[1]

        try:
            if self._on_source_toggle:
                result = await self._on_source_toggle(user_id, source_name)
                text = result if result else f"Source toggled: {html.escape(source_name)}"
            else:
                text = "Source toggle not configured."
        except Exception:
            logger.exception("Error toggling source")
            text = "Error toggling source."

        await query.edit_message_text(text, parse_mode="HTML")

    async def send_post(
        self,
        chat_id: int | None,
        post_id: str,
        source: str,
        category: str,
        score: float,
        reason: str,
        post_text: str,
        post_url: str | None = None,
        extra_buttons: list[InlineKeyboardButton] | None = None,
    ) -> None:
        """Format and send a filtered post with feedback buttons."""
        target = chat_id if chat_id is not None else self.target_chat_id

        text = self._format_post_message(source, category, score, reason, post_text)
        keyboard = self._build_post_keyboard(post_id, post_url, extra_buttons)

        try:
            bot: Bot = self.application.bot
            await bot.send_message(
                chat_id=target,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard if keyboard.inline_keyboard else None,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Failed to send post %s to chat %s", post_id, target)

    async def send_notification(
        self,
        chat_id: int | None,
        message: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        """Send a notification message."""
        target = chat_id if chat_id is not None else self.target_chat_id
        try:
            bot: Bot = self.application.bot
            await bot.send_message(
                chat_id=target,
                text=message,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to send notification to chat %s", target)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        """Edit an existing message."""
        try:
            bot: Bot = self.application.bot
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to edit message %s in chat %s", message_id, chat_id)

    def _format_post_message(
        self,
        source: str,
        category: str,
        score: float,
        reason: str,
        post_text: str,
    ) -> str:
        """Format a post message with HTML."""
        escaped_source = html.escape(source)
        escaped_category = html.escape(category)
        escaped_reason = html.escape(reason)

        score_int = int(score)
        text = (
            f"<b>Source:</b> {escaped_source}\n"
            f"<b>Category:</b> {escaped_category}\n"
            f"<b>Score:</b> {score_int}/100\n"
            f"<b>Reason:</b> {escaped_reason}\n"
            f"\n"
            f"{html.escape(post_text)}"
        )
        return text

    def _format_history_entry(self, post: PostData) -> str:
        """Format a single history entry."""
        source = html.escape(post.get("source") or post.get("channel_name", "Unknown"))
        category = html.escape(post.get("category", "Uncategorized"))
        score = post.get("score", 0)
        text_preview = html.escape(post.get("text", "")[:100])
        if len(post.get("text", "")) > 100:
            text_preview += "..."

        return (
            f"<b>{source}</b> | <i>{category}</i> | "
            f"Score: {score}/100\n"
            f"{text_preview}"
        )

    def _format_settings(self, settings: SettingsData) -> str:
        """Format settings data for display."""
        if not settings:
            return "No settings configured."

        lines = ["<b>Your Settings:</b>\n"]
        for key, value in settings.items():
            escaped_key = html.escape(str(key))
            escaped_value = html.escape(str(value))
            lines.append(f"<b>{escaped_key}:</b> {escaped_value}")
        return "\n".join(lines)

    def _format_stats(self, stats: dict[str, Any]) -> str:
        """Format statistics for display."""
        if not stats:
            return "No statistics available."

        lines = ["<b>Filter Statistics:</b>\n"]
        for key, value in stats.items():
            escaped_key = html.escape(str(key))
            if isinstance(value, float):
                escaped_value = f"{value:.2f}"
            else:
                escaped_value = html.escape(str(value))
            lines.append(f"<b>{escaped_key}:</b> {escaped_value}")
        return "\n".join(lines)

    def _build_post_keyboard(
        self,
        post_id: str,
        post_url: str | None = None,
        extra_buttons: list[InlineKeyboardButton] | None = None,
    ) -> InlineKeyboardMarkup:
        """Build inline keyboard for a post."""
        buttons: list[list[InlineKeyboardButton]] = []

        row = [
            InlineKeyboardButton(
                text="\U0001f44d",
                callback_data=f"feedback_{post_id}_useful",
            ),
            InlineKeyboardButton(
                text="\U0001f44e",
                callback_data=f"feedback_{post_id}_not_useful",
            ),
            InlineKeyboardButton(
                text="\u2b50 Save",
                callback_data=f"save_{post_id}",
            ),
            InlineKeyboardButton(
                text="\U0001f4c2 Move",
                callback_data=f"move_{post_id}",
            ),
        ]
        buttons.append(row)

        if post_url:
            buttons.append(
                [InlineKeyboardButton(text="View Original", url=post_url)]
            )

        if extra_buttons:
            buttons.append(extra_buttons)

        return InlineKeyboardMarkup(buttons)

    def _build_settings_keyboard(self, settings: SettingsData) -> InlineKeyboardMarkup | None:
        """Build inline keyboard for settings."""
        if not settings:
            return None

        buttons: list[list[InlineKeyboardButton]] = []
        for key, value in settings.items():
            escaped_key = html.escape(str(key))
            status = "\u2705" if value else "\u274c"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{escaped_key}: {status}",
                        callback_data=f"settings_{key}",
                    )
                ]
            )

        return InlineKeyboardMarkup(buttons) if buttons else None

    async def run(self) -> None:
        """Start the bot with polling."""
        app = self.create_application()
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        try:
            await app.updater.wait()
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    async def stop(self) -> None:
        """Gracefully stop the bot."""
        if self._app and self._app.running:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
