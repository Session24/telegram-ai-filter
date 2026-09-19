"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import PostAnalysis


class AIProviderError(Exception):
    """Base exception for AI provider errors."""


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def analyze_post(
        self,
        post_text: str,
        system_prompt: str,
    ) -> PostAnalysis:
        """Analyze a Telegram post and return structured classification."""
        ...

    async def close(self) -> None:
        """Clean up provider resources."""
        pass
