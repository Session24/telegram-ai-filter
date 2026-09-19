"""OpenAI-compatible AI provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from .provider import AIProvider, AIProviderError
from .schemas import ContentType, ImportanceLevel, PostAnalysis

logger = logging.getLogger(__name__)

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "useful": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "category": {"type": "string"},
        "subcategory": {"type": "string"},
        "content_type": {
            "type": "string",
            "enum": [ct.value for ct in ContentType],
        },
        "importance": {
            "type": "string",
            "enum": [il.value for il in ImportanceLevel],
        },
        "reason": {"type": "string"},
        "suggested_folder": {"type": "string"},
    },
    "required": [
        "useful",
        "score",
        "category",
        "content_type",
        "importance",
        "reason",
    ],
    "additionalProperties": False,
}


class OpenAICompatibleProvider(AIProvider):
    """AI provider for OpenAI-compatible APIs (OpenAI, NVIDIA, OpenRouter, LM Studio, etc.)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_retries: int = 3,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

    async def analyze_post(
        self,
        post_text: str,
        system_prompt: str,
    ) -> PostAnalysis:
        if not post_text.strip():
            raise AIProviderError("Post has no analyzable text")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": post_text[:12000]},
            ],
            "temperature": 0,
            "max_tokens": 500,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "telegram_post_analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                },
            },
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )

                    if response.status_code == 401:
                        raise AIProviderError(
                            "Invalid API key. Check AI_API_KEY in .env."
                        )
                    if response.status_code == 403:
                        raise AIProviderError(
                            "Access forbidden. Check AI_BASE_URL and API key permissions."
                        )
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "30"))
                        logger.warning(
                            "Rate limited by AI provider, retrying after %ss",
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    if response.status_code >= 500:
                        raise AIProviderError(
                            f"AI provider error (HTTP {response.status_code}). "
                            "Try again later."
                        )

                    response.raise_for_status()
                    response_data = response.json()
                    content = response_data["choices"][0]["message"]["content"]

                    if not isinstance(content, str) or not content.strip():
                        raise AIProviderError("AI returned empty content")

                    return self._parse_response(content)

            except AIProviderError:
                raise
            except httpx.TimeoutException:
                logger.warning(
                    "AI request timed out (attempt %s/%s)",
                    attempt,
                    self.max_retries,
                )
                last_error = httpx.TimeoutException("Request timed out")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ) as exc:
                logger.warning(
                    "AI request failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc.__class__.__name__,
                )
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)

        raise AIProviderError(
            f"AI is unavailable after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_response(self, raw_content: str) -> PostAnalysis:
        """Parse and validate AI JSON response into PostAnalysis."""
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            start = raw_content.find("{")
            end = raw_content.rfind("}")

            if start == -1 or end <= start:
                raise AIProviderError("AI returned invalid JSON") from exc

            try:
                result = json.loads(raw_content[start : end + 1])
            except json.JSONDecodeError as fallback_exc:
                raise AIProviderError("AI returned invalid JSON") from fallback_exc

        if not isinstance(result, dict):
            raise AIProviderError("AI returned a non-object JSON value")

        # Validate required fields
        useful = result.get("useful")
        if not isinstance(useful, bool):
            raise AIProviderError("Invalid 'useful' field in AI response")

        score = result.get("score")
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or not 0 <= score <= 100
        ):
            raise AIProviderError("Invalid 'score' field in AI response")

        category = result.get("category")
        if not isinstance(category, str) or not category.strip():
            raise AIProviderError("Missing 'category' in AI response")

        content_type_str = result.get("content_type", "OTHER")
        try:
            content_type = ContentType(content_type_str)
        except ValueError:
            content_type = ContentType.OTHER

        importance_str = result.get("importance", "medium")
        try:
            importance = ImportanceLevel(importance_str)
        except ValueError:
            importance = ImportanceLevel.MEDIUM

        reason = result.get("reason", "")
        if not isinstance(reason, str) or not reason.strip():
            reason = "No reason provided"

        subcategory = result.get("subcategory")
        if subcategory is not None and (
            not isinstance(subcategory, str) or not subcategory.strip()
        ):
            subcategory = None

        suggested_folder = result.get("suggested_folder")
        if suggested_folder is not None and (
            not isinstance(suggested_folder, str) or not suggested_folder.strip()
        ):
            suggested_folder = None

        return PostAnalysis(
            useful=useful,
            score=score,
            category=category.strip(),
            subcategory=subcategory.strip() if subcategory else None,
            content_type=content_type,
            importance=importance,
            reason=reason.strip(),
            suggested_folder=suggested_folder.strip() if suggested_folder else None,
        )
