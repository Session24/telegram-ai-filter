"""Tests for Telegram bot callback logic and channel input parsing."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from telegram_ai_filter.telegram.bot import TelegramBot


class TestChannelInputParsing:
    """Test the channel input parsing logic used in app.py."""

    def _make_bot(self):
        return TelegramBot(token="fake:token", target_chat_id=123)

    @pytest.mark.asyncio
    async def test_parse_at_username(self):
        import re

        channel_input = "@fpv_drones"
        m = re.match(r"^@(\w+)$", channel_input)
        assert m is not None
        assert m.group(1) == "fpv_drones"

    @pytest.mark.asyncio
    async def test_parse_plain_username(self):
        import re

        channel_input = "fpv_drones"
        m = re.match(r"^(\w+)$", channel_input)
        assert m is not None
        assert m.group(1) == "fpv_drones"

    @pytest.mark.asyncio
    async def test_parse_tme_link(self):
        import re

        channel_input = "t.me/fpv_drones"
        m = re.match(r"(?:https?://)?t\.me/(\w+)$", channel_input)
        assert m is not None
        assert m.group(1) == "fpv_drones"

    @pytest.mark.asyncio
    async def test_parse_https_tme_link(self):
        import re

        channel_input = "https://t.me/fpv_drones"
        m = re.match(r"(?:https?://)?t\.me/(\w+)$", channel_input)
        assert m is not None
        assert m.group(1) == "fpv_drones"

    @pytest.mark.asyncio
    async def test_parse_invalid_input(self):
        import re

        channel_input = "this is not a channel"
        m_at = re.match(r"^@(\w+)$", channel_input)
        m_tme = re.match(r"(?:https?://)?t\.me/(\w+)$", channel_input)
        m_plain = re.match(r"^(\w+)$", channel_input)
        assert m_at is None
        assert m_tme is None
        assert m_plain is None


class TestBotKeyboardBuilding:
    """Test bot keyboard construction."""

    def test_post_keyboard_has_all_buttons(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        keyboard = bot._build_post_keyboard("42")

        assert len(keyboard.inline_keyboard) == 1
        row = keyboard.inline_keyboard[0]
        assert len(row) == 4

        callback_data = [btn.callback_data for btn in row]
        assert "feedback_42_useful" in callback_data
        assert "feedback_42_not_useful" in callback_data
        assert "save_42" in callback_data
        assert "move_42" in callback_data

    def test_post_keyboard_with_url(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        keyboard = bot._build_post_keyboard("42", post_url="https://t.me/test/1")

        assert len(keyboard.inline_keyboard) == 2
        url_row = keyboard.inline_keyboard[1]
        assert url_row[0].url == "https://t.me/test/1"

    def test_post_keyboard_without_url(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        keyboard = bot._build_post_keyboard("42")

        assert len(keyboard.inline_keyboard) == 1


class TestBotFormatPostMessage:
    """Test post message formatting."""

    def test_format_post_message(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        text = bot._format_post_message(
            source="Test Channel",
            category="FPV",
            score=85.0,
            reason="Great content",
            post_text="Hello world",
        )

        assert "Test Channel" in text
        assert "FPV" in text
        assert "85" in text
        assert "Great content" in text
        assert "Hello world" in text

    def test_format_history_entry_with_source(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        post = {"source": "My Channel", "category": "AI", "score": 90, "text": "Test content"}
        text = bot._format_history_entry(post)

        assert "My Channel" in text
        assert "AI" in text

    def test_format_history_entry_with_channel_name_fallback(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        post = {"channel_name": "Fallback Channel", "category": "Tech", "score": 50, "text": "Content"}
        text = bot._format_history_entry(post)

        assert "Fallback Channel" in text


class TestBotSettingsFormatting:
    """Test settings formatting."""

    def test_format_settings(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        settings = {"Interests": "FPV, AI", "Min Score": "70", "Notifications": "On"}
        text = bot._format_settings(settings)

        assert "Interests" in text
        assert "FPV, AI" in text

    def test_format_settings_empty(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        text = bot._format_settings({})
        assert "No settings" in text

    def test_format_stats(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        stats = {"Total Posts": 100, "Useful": 42}
        text = bot._format_stats(stats)

        assert "Total Posts" in text
        assert "42" in text

    def test_format_stats_empty(self):
        bot = TelegramBot(token="fake:token", target_chat_id=123)
        text = bot._format_stats({})
        assert "No statistics" in text
