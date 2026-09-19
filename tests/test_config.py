"""Tests for configuration and prompts."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from telegram_ai_filter.config.prompts import build_system_prompt, FEEDBACK_REASONS


class TestPromptBuilding:
    def test_builds_prompt_with_interests(self):
        prompt = build_system_prompt(interests="FPV, AI, Programming")
        assert "FPV" in prompt
        assert "AI" in prompt
        assert "Programming" in prompt

    def test_builds_prompt_without_interests(self):
        prompt = build_system_prompt(interests="")
        assert "Not specified" in prompt

    def test_builds_prompt_with_excluded_topics(self):
        prompt = build_system_prompt(
            interests="FPV",
            excluded_topics="Sales, Memes",
        )
        assert "Sales" in prompt
        assert "Memes" in prompt

    def test_builds_prompt_with_folders(self):
        prompt = build_system_prompt(
            interests="FPV",
            folders="FPV - Drone racing content\nAI - Machine learning",
        )
        assert "FPV - Drone racing content" in prompt

    def test_builds_prompt_with_learned_preferences(self):
        prompt = build_system_prompt(
            interests="FPV",
            learned_preferences="User prefers technical content over news",
        )
        assert "User prefers technical content" in prompt


class TestFeedbackReasons:
    def test_has_all_reasons(self):
        expected_keys = [
            "not_my_topic",
            "too_shallow",
            "advertisement",
            "already_know",
            "not_relevant",
            "other",
        ]
        for key in expected_keys:
            assert key in FEEDBACK_REASONS

    def test_reasons_are_strings(self):
        for key, value in FEEDBACK_REASONS.items():
            assert isinstance(value, str)
            assert len(value) > 0
