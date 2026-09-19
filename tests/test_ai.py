"""Tests for AI response parsing and validation."""

import json
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from telegram_ai_filter.ai.openai_compatible import OpenAICompatibleProvider
from telegram_ai_filter.ai.schemas import ContentType, ImportanceLevel
from telegram_ai_filter.ai.provider import AIProviderError


@pytest.fixture
def provider():
    return OpenAICompatibleProvider(
        base_url="http://localhost:1234/v1",
        api_key="test-key",
        model="test-model",
    )


class TestParseResponse:
    def test_valid_useful_post(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 85,
            "category": "FPV",
            "subcategory": "Tiny Whoop",
            "content_type": "TECHNICAL",
            "importance": "high",
            "reason": "Practical guide on Tiny Whoop rate tuning",
            "suggested_folder": "FPV / Tiny Whoop",
        })
        result = provider._parse_response(response)

        assert result.useful is True
        assert result.score == 85
        assert result.category == "FPV"
        assert result.subcategory == "Tiny Whoop"
        assert result.content_type == ContentType.TECHNICAL
        assert result.importance == ImportanceLevel.HIGH
        assert result.reason == "Practical guide on Tiny Whoop rate tuning"
        assert result.suggested_folder == "FPV / Tiny Whoop"

    def test_valid_not_useful_post(self, provider):
        response = json.dumps({
            "useful": False,
            "score": 20,
            "category": "FPV",
            "content_type": "SALE",
            "importance": "low",
            "reason": "This is an advertisement for FPV propellers",
        })
        result = provider._parse_response(response)

        assert result.useful is False
        assert result.score == 20
        assert result.content_type == ContentType.SALE
        assert result.importance == ImportanceLevel.LOW
        assert result.subcategory is None
        assert result.suggested_folder is None

    def test_invalid_json(self, provider):
        with pytest.raises(AIProviderError, match="invalid JSON"):
            provider._parse_response("not json at all")

    def test_json_in_markdown_block(self, provider):
        response = '```json\n{"useful": true, "score": 50, "category": "Tech", "content_type": "OTHER", "importance": "medium", "reason": "test"}\n```'
        result = provider._parse_response(response)
        assert result.useful is True
        assert result.score == 50

    def test_non_object_json(self, provider):
        with pytest.raises(AIProviderError, match="non-object"):
            provider._parse_response('"just a string"')

    def test_missing_required_field(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 50,
            # missing category
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "test",
        })
        with pytest.raises(AIProviderError, match="Missing"):
            provider._parse_response(response)

    def test_invalid_score_type(self, provider):
        response = json.dumps({
            "useful": True,
            "score": "high",
            "category": "Tech",
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "test",
        })
        with pytest.raises(AIProviderError, match="Invalid.*score"):
            provider._parse_response(response)

    def test_score_out_of_range(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 150,
            "category": "Tech",
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "test",
        })
        with pytest.raises(AIProviderError, match="Invalid.*score"):
            provider._parse_response(response)

    def test_boolean_score_rejected(self, provider):
        response = json.dumps({
            "useful": True,
            "score": True,
            "category": "Tech",
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "test",
        })
        with pytest.raises(AIProviderError, match="Invalid.*score"):
            provider._parse_response(response)

    def test_invalid_content_type_falls_back_to_other(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 50,
            "category": "Tech",
            "content_type": "INVALID_TYPE",
            "importance": "medium",
            "reason": "test",
        })
        result = provider._parse_response(response)
        assert result.content_type == ContentType.OTHER

    def test_invalid_importance_falls_back_to_medium(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 50,
            "category": "Tech",
            "content_type": "OTHER",
            "importance": "super_important",
            "reason": "test",
        })
        result = provider._parse_response(response)
        assert result.importance == ImportanceLevel.MEDIUM

    def test_empty_category_rejected(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 50,
            "category": "",
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "test",
        })
        with pytest.raises(AIProviderError, match="Missing.*category"):
            provider._parse_response(response)

    def test_empty_reason_uses_default(self, provider):
        response = json.dumps({
            "useful": True,
            "score": 50,
            "category": "Tech",
            "content_type": "OTHER",
            "importance": "medium",
            "reason": "",
        })
        result = provider._parse_response(response)
        assert result.reason == "No reason provided"

    def test_all_content_types(self, provider):
        for ct in ContentType:
            response = json.dumps({
                "useful": True,
                "score": 50,
                "category": "Test",
                "content_type": ct.value,
                "importance": "medium",
                "reason": "test",
            })
            result = provider._parse_response(response)
            assert result.content_type == ct

    def test_all_importance_levels(self, provider):
        for il in ImportanceLevel:
            response = json.dumps({
                "useful": True,
                "score": 50,
                "category": "Test",
                "content_type": "OTHER",
                "importance": il.value,
                "reason": "test",
            })
            result = provider._parse_response(response)
            assert result.importance == il

    def test_score_boundaries(self, provider):
        for score in [0, 1, 29, 30, 50, 69, 70, 84, 85, 99, 100]:
            response = json.dumps({
                "useful": score >= 50,
                "score": score,
                "category": "Test",
                "content_type": "OTHER",
                "importance": "medium",
                "reason": "test",
            })
            result = provider._parse_response(response)
            assert result.score == score
