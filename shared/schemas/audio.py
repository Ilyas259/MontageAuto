"""
Schémas Pydantic — Audio Design (Agent #4)
Version: 1.0.0
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from decimal import Decimal
from enum import Enum


class Mood(str, Enum):
    """Humeur musicale supportée par Epidemic Sound."""
    ENERGETIC = "energetic"
    CALM = "calm"
    DRAMATIC = "dramatic"
    UPBEAT = "upbeat"
    SUSPENSE = "suspense"
    INSPIRATIONAL = "inspirational"
    CORPORATE = "corporate"
    FUN = "fun"
    SAD = "sad"
    NEUTRAL = "neutral"


class MusicTrack(BaseModel):
    """Piste musicale de fond."""
    track_id: str
    title: str
    artist: Optional[str] = None
    duration: Decimal = Field(..., ge=0)
    mood: Mood = Mood.NEUTRAL
    bpm: Optional[int] = Field(None, ge=40, le=200)
    source: Literal["epidemic_sound", "local"] = "epidemic_sound"
    local_path: Optional[str] = None
    loop: bool = False
    fade_in: Decimal = Field(default=Decimal("0.5"), ge=0)
    fade_out: Decimal = Field(default=Decimal("1.0"), ge=0)


class SoundEffect(BaseModel):
    """Effet sonore."""
    effect_id: str
    name: str
    timestamp: Decimal = Field(..., ge=0)
    duration: Decimal = Field(..., ge=0.1, le=5.0)
    volume: float = Field(default=0.7, ge=0.0, le=1.0)
    category: Literal[
        "transition", "emphasis", "ambient", "ui",
        "comedy", "notification", "nature", "other"
    ] = "other"
    source: Literal["epidemic_sound", "local", "generated"] = "local"
    local_path: Optional[str] = None


class DuckingConfig(BaseModel):
    """Configuration du ducking automatique (baisse du volume musique pendant la parole)."""
    enabled: bool = True
    attack_ms: int = Field(default=50, ge=10, le=500)
    release_ms: int = Field(default=200, ge=50, le=1000)
    threshold_db: float = Field(default=-30.0, ge=-60.0, le=0.0)
    reduction_db: float = Field(default=-12.0, ge=-30.0, le=0.0)
    mix_ratio: float = Field(default=0.85, ge=0.0, le=1.0)


class AudioConfig(BaseModel):
    """Configuration complète du mixage audio (Agent #4)."""
    ducking: DuckingConfig = DuckingConfig()
    music_volume: float = Field(default=0.25, ge=0.0, le=1.0)
    sfx_volume: float = Field(default=0.7, ge=0.0, le=1.0)
    voice_volume: float = Field(default=1.0, ge=0.0, le=1.5)
    compressor_threshold_db: float = -16.0
    compressor_ratio: float = 3.0
    normalize_loudness: bool = True
    target_loudness_lufs: float = -14.0
    output_format: Literal["wav", "aac", "mp3"] = "aac"
    output_bitrate: Literal["128k", "192k", "256k", "320k"] = "192k"


class AudioTimelineEvent(BaseModel):
    """Événement sur la timeline audio."""
    timestamp: Decimal = Field(..., ge=0)
    type: Literal[
        "music_start", "music_stop", "music_swap",
        "sfx_play", "sfx_stop",
        "duck_start", "duck_stop",
        "voice_boost", "silence"
    ]
    params: Optional[dict] = None


class AudioMix(BaseModel):
    """Plan de mixage audio complet."""
    schema_version: str = "1.0.0"
    music: Optional[MusicTrack] = None
    sound_effects: List[SoundEffect] = Field(default_factory=list)
    timeline: List[AudioTimelineEvent] = Field(default_factory=list)
    config: AudioConfig = AudioConfig()


class AudioMetadata(BaseModel):
    """Métadonnées de l'audio mixé final (sortie Agent #4 → Agent #5)."""
    schema_version: str = "1.0.0"
    source_video_duration: Decimal
    output_duration: Decimal
    has_voice: bool
    has_music: bool
    sfx_count: int
    average_loudness_lufs: float
    peak_db: float
    dynamic_range_db: float
    sync_verified: bool
    sync_drift_ms: Optional[float] = None
