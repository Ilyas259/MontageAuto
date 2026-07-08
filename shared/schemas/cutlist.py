"""
Schémas Pydantic — Cut List & Dérushage (Agent #2)
Version: 1.0.0
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from decimal import Decimal


class ErrorDetection(BaseModel):
    """Une erreur de parole détectée par le LLM (Agent #2)."""
    type: Literal["false_start", "stutter", "filler",
                  "dead_pause", "repetition"]
    start_timestamp: Decimal = Field(..., ge=0)
    end_timestamp: Decimal = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., max_length=200)

    class Config:
        frozen = True


class KeptSegment(BaseModel):
    """Segment vidéo à conserver dans le montage final."""
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    duration: Decimal = Field(..., ge=0)
    text: str
    speaker: Optional[str] = None
    type: Literal["keep"] = "keep"
    confidence: float = Field(..., ge=0.0, le=1.0)


class RemovedSegment(BaseModel):
    """Segment vidéo à supprimer du montage final."""
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    duration: Decimal = Field(..., ge=0)
    type: Literal["false_start", "stutter", "filler",
                  "dead_pause", "repetition", "silence"]
    reason: str


class BRollSuggestion(BaseModel):
    """Suggestion de B-roll à un moment précis."""
    timestamp: Decimal = Field(..., ge=0)
    duration: Decimal = Field(..., ge=1.0, le=10.0)
    concept: str = Field(..., max_length=100)
    placement: Literal["overlay", "fullscreen", "split"] = "overlay"
    priority: Literal["low", "medium", "high"] = "medium"
    reason: str


class CutList(BaseModel):
    """Structure complète de la liste de montage (sortie Agent #2 → Agent #3)."""
    schema_version: str = "1.0.0"
    source_duration: Decimal = Field(..., ge=0)
    kept_segments: List[KeptSegment]
    removed_segments: List[RemovedSegment] = Field(default_factory=list)
    b_roll_suggestions: List[BRollSuggestion] = Field(default_factory=list)
    total_kept_duration: Decimal = Field(..., ge=0)
    total_removed_duration: Decimal = Field(..., ge=0)
    compression_ratio: float = Field(..., ge=0.0, le=1.0)
    subtitle_style: Literal["karaoke", "block", "none"] = "block"
    subtitle_custom: Optional[dict] = None

    @property
    def is_over_derushed(self) -> bool:
        """Alerte si plus de 50% du contenu a été coupé."""
        return self.compression_ratio < 0.5


class CleanScript(BaseModel):
    """Script nettoyé (sortie Agent #2 → Agent #3 pour sous-titres)."""
    schema_version: str = "1.0.0"
    paragraphs: List[str]
    original_duration: Decimal
    cleaned_word_count: int
    filler_words_removed: int
