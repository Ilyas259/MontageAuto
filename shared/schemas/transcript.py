"""
Schémas Pydantic — Transcription (Agent #1)
Version: 1.0.0
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from enum import Enum


class Word(BaseModel):
    """Mot individuel avec timestamp précis (word-level alignment)."""
    text: str = Field(..., min_length=1)
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0, default=0.95)
    speaker: Optional[str] = None

    class Config:
        frozen = True


class VADSegment(BaseModel):
    """Segment de détection d'activité vocale (Voice Activity Detection)."""
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    type: str = Field(..., pattern="^(speech|silence|noise)$")
    energy: Optional[float] = None


class Sentence(BaseModel):
    """Phrase logique (regroupement de mots par ponctuation/changement de sujet)."""
    text: str
    words: List[Word] = Field(default_factory=list)
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    speaker: Optional[str] = None
    is_punctuation_end: bool = False
    patterns_detected: List[str] = Field(default_factory=list)
    has_silence_after: bool = False
    silence_duration: Optional[Decimal] = None


class SpeakerSegment(BaseModel):
    """Segment attribué à un locuteur unique."""
    speaker: str
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    text: str


class TranscriptConfig(BaseModel):
    """Configuration du module de transcription (Agent #1)."""
    scribe_api_key: str = Field(..., repr=False)
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    vad_aggressiveness: int = Field(default=3, ge=1, le=3)
    diarize: bool = False
    language: str = "fr"
    align_words: bool = True
    compute_confidence: bool = True
    silence_threshold_db: int = -40
    min_speech_duration_ms: int = 100
    min_silence_duration_ms: int = 300


class TranscriptionMetadata(BaseModel):
    """Métadonnées sur le processus de transcription."""
    source_filename: str
    source_duration: Decimal
    source_samplerate: int
    source_channels: int
    total_words: int
    total_silence: Decimal
    average_speech_rate: float
    model_used: str
    processing_time_s: float
    pipeline_version: str = "1.0.0"


class TranscriptionOutput(BaseModel):
    """Structure complète de sortie de l'Agent #1."""
    schema_version: str = "1.0.0"
    segments: List[Sentence]
    words: List[Word] = Field(default_factory=list)
    speakers: List[SpeakerSegment] = Field(default_factory=list)
    vad_segments: List[VADSegment] = Field(default_factory=list)
    metadata: TranscriptionMetadata
