"""AI response schemas."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ContentType(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    NEWS = "NEWS"
    TUTORIAL = "TUTORIAL"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    COMPETITION = "COMPETITION"
    PRODUCT = "PRODUCT"
    SALE = "SALE"
    ADVERTISEMENT = "ADVERTISEMENT"
    MEME = "MEME"
    DISCUSSION = "DISCUSSION"
    OTHER = "OTHER"


class ImportanceLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PostAnalysis:
    useful: bool
    score: int
    category: str
    subcategory: str | None
    content_type: ContentType
    importance: ImportanceLevel
    reason: str
    suggested_folder: str | None

    def to_dict(self) -> dict:
        return {
            "useful": self.useful,
            "score": self.score,
            "category": self.category,
            "subcategory": self.subcategory,
            "content_type": self.content_type.value,
            "importance": self.importance.value,
            "reason": self.reason,
            "suggested_folder": self.suggested_folder,
        }
