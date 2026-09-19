"""Telegram channel reader using Telethon (user account)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat

logger = logging.getLogger(__name__)


def extract_post(message: Any, chat: Any) -> dict[str, object] | None:
    """Extract post data from a Telethon message event."""
    text = message.message or ""
    if not text.strip():
        return None

    media = getattr(message, "media", None)
    photo = bool(media and getattr(message, "photo", None))
    video = bool(media and getattr(message, "video", None))

    username = getattr(chat, "username", None)
    url = f"https://t.me/{username}/{message.id}" if username else None

    telegram_created_at = None
    if message.date:
        telegram_created_at = message.date

    return {
        "channel_id": chat.id,
        "telegram_message_id": message.id,
        "channel_name": getattr(chat, "title", None) or username or str(chat.id),
        "channel_username": username,
        "text": text,
        "message_url": url,
        "has_photo": photo,
        "has_video": video,
        "telegram_created_at": telegram_created_at,
    }


PostCallback = Callable[[dict[str, object]], Coroutine[Any, Any, None]]


class ChannelReader:
    """Reads messages from Telegram channels using a user account (Telethon)."""

    def __init__(self, api_id: int, api_hash: str, session_name: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client: TelegramClient | None = None
        self._callback: PostCallback | None = None
        self._monitored_channels: list[str | int] = []

    async def start(self) -> None:
        """Connect and authorize the Telegram client."""
        self.client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash,
            device_model="Telegram AI Filter",
        )
        await self.client.start()
        me = await self.client.get_me()
        logger.info(
            "Telegram user client connected as %s (ID: %s)",
            getattr(me, "first_name", "unknown"),
            getattr(me, "id", "unknown"),
        )

    def set_channels(self, channels: list[str | int]) -> None:
        """Set the list of channels to monitor."""
        self._monitored_channels = channels

    def register_handler(self, callback: PostCallback) -> None:
        """Register a callback for new messages from monitored channels."""
        self._callback = callback

        @self.client.on(events.NewMessage(chats=self._monitored_channels))
        async def handler(event):
            try:
                chat = await event.get_chat()
                post = extract_post(event.message, chat)
                if post and self._callback:
                    await self._callback(post)
            except Exception:
                logger.exception("Error processing new message event")

    async def resolve_channel(self, channel_ref: str) -> dict[str, object] | None:
        """Resolve a channel reference (username or link) to channel info."""
        if not self.client:
            raise RuntimeError("Client not started")

        try:
            entity = await self.client.get_entity(channel_ref)
            if isinstance(entity, (Channel, Chat)):
                return {
                    "id": entity.id,
                    "username": getattr(entity, "username", None),
                    "title": getattr(entity, "title", str(entity.id)),
                }
        except Exception as exc:
            logger.warning("Failed to resolve channel '%s': %s", channel_ref, exc)
        return None

    async def run_until_disconnected(self) -> None:
        """Run until the client disconnects."""
        if self.client:
            await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Disconnect the client."""
        if self.client:
            await self.client.disconnect()
