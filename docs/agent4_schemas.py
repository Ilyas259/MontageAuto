"""
Agent #4 — Design Audio
Schémas Pydantic v2.7+ — Modèles internes et contrats du module audio.

Ce fichier contient tous les modèles Pydantic pour l'Agent #4 :
- Entrée : EditMetadata (depuis Agent #3)
- Internes : NarrativeBeat, SoundPlacement, MusicTrack, SoundEffect
- Configuration : AudioConfig, AudioMixConfig, EpidemicSoundConfig
- Sortie : AudioMetadata, AudioReport (vers Agent #5)

Utilisation :
    from agents.agent4_audio.schemas import (
        NarrativeBeat, SoundPlacement, MusicTrack,
        AudioConfig, AudioReport, AudioMetadata
    )
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from pathlib import Path
from enum import Enum


# =============================================================================
# Énumérations
# =============================================================================

class NarrativeBeatType(str, Enum):
    """Type de battement narratif détecté dans le script."""
    TRANSITION_SCENE = "transition_scene"
    KEY_POINT = "key_point"
    HUMOR_PUNCHLINE = "humor_punchline"
    SUBJECT_CHANGE = "subject_change"
    VIDEO_START = "video_start"
    VIDEO_END = "video_end"
    EMPHASIS = "emphasis"
    PAUSE_DRAMATIC = "pause_dramatic"
    QUESTION = "question"
    LIST_ITEM = "list_item"


class SFXCategory(str, Enum):
    """Catégorie d'effet sonore."""
    TRANSITION_WHOOSH = "transition_whoosh"
    TRANSITION_SWIPE = "transition_swipe"
    TRANSITION_DING = "transition_ding"
    ACCENT_DING = "accent_ding"
    ACCENT_BELL = "accent_bell"
    ACCENT_CHIME = "accent_chime"
    HUMOR_BOING = "humor_boing"
    HUMOR_LAUGH = "humor_laugh"
    HUMOR_GLITCH = "humor_glitch"
    EMPHASIS_BOOM = "emphasis_boom"
    EMPHASIS_RISER = "emphasis_riser"
    INTRO_OPENER = "intro_opener"
    OUTRO_CLOSER = "outro_closer"
    AMBIENCE = "ambience"
    UI_CLICK = "ui_click"
    SUBTLE_AIR = "subtle_air"


class MusicMood(str, Enum):
    """Ambiance musicale."""
    HAPPY = "happy"
    SAD = "sad"
    ENERGETIC = "energetic"
    NEUTRAL = "neutral"
    DRAMATIC = "dramatic"
    CALM = "calm"
    PROFESSIONAL = "professional"
    INSPIRATIONAL = "inspirational"
    SUSPENSE = "suspense"


class MusicGenre(str, Enum):
    """Genre musical."""
    CINEMATIC = "cinematic"
    ELECTRONIC = "electronic"
    ACOUSTIC = "acoustic"
    AMBIENT = "ambient"
    JAZZ = "jazz"
    LO_FI = "lo_fi"
    UPBEAT = "upbeat"
    CORPORATE = "corporate"


# =============================================================================
# Analyse narrative
# =============================================================================

class NarrativeBeat(BaseModel):
    """Un battement narratif détecté dans le script.

    Attributes:
        type: Type de battement (transition, point clé, humour...)
        timestamp: Position dans la vidéo montée (secondes)
        duration: Durée estimée du moment (secondes)
        text: Texte associé à ce battement
        importance: Importance narrative de 0.0 à 1.0
        confidence: Confiance de la détection de 0.0 à 1.0
        segment_index: Index du segment KeptSegment associé (optionnel)
    """
    type: NarrativeBeatType
    timestamp: float = Field(..., ge=0.0, description="Timestamp dans la vidéo montée (secondes)")
    duration: float = Field(default=0.5, ge=0.0, description="Durée estimée du moment")
    text: str = Field(default="", description="Texte associé à ce battement")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance narrative 0-1")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confiance de la détection")
    segment_index: int | None = Field(default=None, description="Index du segment KeptSegment associé")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "key_point",
                "timestamp": 12.5,
                "duration": 1.0,
                "text": "ce point est absolument essentiel",
                "importance": 0.9,
                "confidence": 0.85,
                "segment_index": 3,
            }
        }


class BeatAnalysisResult(BaseModel):
    """Résultat complet de l'analyse narrative du script."""
    beats: list[NarrativeBeat] = Field(default_factory=list, description="Tous les battements détectés")
    total_duration: float = Field(..., ge=0.0, description="Durée totale de la vidéo (secondes)")
    pace: str = Field(default="medium", description="Rythme : 'slow', 'medium', 'fast'")
    overall_mood: str = Field(default="neutral", description="Mood général détecté")
    estimated_bpm: float | None = Field(default=None, description="BPM estimé si disponible")


# =============================================================================
# Effets sonores
# =============================================================================

class SoundEffect(BaseModel):
    """Un effet sonore téléchargé/préparé.

    Attributes:
        effect_id: Identifiant unique de l'effet
        category: Catégorie SFX
        source: Source de l'effet (Epidemic Sound, CC0, généré)
        epidemic_sound_id: ID sur Epidemic Sound (optionnel)
        title: Titre descriptif
        local_path: Chemin local du fichier audio
        duration: Durée en secondes
        sample_rate: Taux d'échantillonnage (Hz)
        original_has_silence_start: True si silence détecté au début
        loopable: True si l'effet peut être joué en boucle
        prep_trim_start: Secondes à supprimer au début
        prep_trim_end: Secondes à supprimer à la fin
        prep_gain_db: Ajustement de gain appliqué (dB)
    """
    effect_id: str = Field(..., description="Identifiant unique")
    category: SFXCategory
    source: Literal["epidemic_sound", "cc0_library", "generated"] = "epidemic_sound"
    epidemic_sound_id: str | None = Field(default=None, description="ID Epidemic Sound")
    title: str = ""
    local_path: Path | None = None
    duration: float = Field(default=0.0, ge=0.0)
    sample_rate: int = 48000
    original_has_silence_start: bool = False
    loopable: bool = False
    prep_trim_start: float = 0.0
    prep_trim_end: float = 0.0
    prep_gain_db: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "effect_id": "sfx_transition_0",
                "category": "transition_whoosh",
                "source": "epidemic_sound",
                "epidemic_sound_id": "es_12345",
                "title": "Soft Whoosh 01",
                "local_path": "/data/audio/cache/epidemic_sound/es_12345.mp3",
                "duration": 0.7,
                "sample_rate": 48000,
                "original_has_silence_start": True,
                "loopable": False,
                "prep_trim_start": 0.05,
            }
        }


class SoundPlacement(BaseModel):
    """Placement d'un effet sonore sur la timeline.

    Attributes:
        effect: L'effet sonore à placer
        timestamp: Début dans la vidéo montée (secondes)
        duration: Durée (None = durée naturelle de l'effet)
        volume: Volume de 0.0 à 1.0
        fade_in: Durée du fade in (secondes)
        fade_out: Durée du fade out (secondes)
        duck_voice: Si True, ducker la voix pendant l'effet
        category: Catégorie SFX (copie rapide pour filtrage)
    """
    effect: SoundEffect
    timestamp: float = Field(..., ge=0.0, description="Début dans la vidéo montée (s)")
    duration: float | None = Field(default=None, description="Durée (None = durée naturelle)")
    volume: float = Field(default=0.3, ge=0.0, le=1.0, description="Volume 0.0-1.0")
    fade_in: float = Field(default=0.02, ge=0.0, description="Fade in (s)")
    fade_out: float = Field(default=0.05, ge=0.0, description="Fade out (s)")
    duck_voice: bool = Field(default=False, description="Ducker la voix pendant l'effet")
    category: SFXCategory


# =============================================================================
# Musique
# =============================================================================

class MusicTrack(BaseModel):
    """Piste de musique de fond.

    Attributes:
        track_id: Identifiant unique
        epidemic_sound_id: ID Epidemic Sound (si applicable)
        title: Titre du morceau
        artist: Artiste
        local_path: Chemin local du fichier
        duration: Durée en secondes (> 0)
        bpm: BPM (optionnel)
        key: Tonalité musicale (ex: "C major")
        mood: Ambiance musicale
        genre: Genre musical
        loop_start: Début de la zone de boucle (secondes)
        loop_end: Fin de la zone de boucle (secondes)
        is_loopable: True si le morceau a des loop points valides
        fade_in: Durée du fade in à l'application (secondes)
        fade_out: Durée du fade out (secondes)
        volume_db: Volume relatif à la voix (dB)
        source: Source du morceau
    """
    track_id: str = Field(..., description="Identifiant unique")
    epidemic_sound_id: str | None = None
    title: str = ""
    artist: str = ""
    local_path: Path
    duration: float = Field(..., gt=0.0)
    bpm: float | None = None
    key: str | None = None
    mood: MusicMood = MusicMood.NEUTRAL
    genre: MusicGenre = MusicGenre.ELECTRONIC
    loop_start: float = Field(default=0.0, description="Début de la boucle (s)")
    loop_end: float = Field(default=0.0, description="Fin de la boucle (s)")
    is_loopable: bool = False
    fade_in: float = Field(default=2.0, ge=0.0)
    fade_out: float = Field(default=3.0, ge=0.0)
    volume_db: float = Field(default=-20.0, description="Volume relatif à la voix (dB)")
    source: Literal["epidemic_sound", "cc0_library"] = "epidemic_sound"


# =============================================================================
# Configuration
# =============================================================================

class DuckingConfig(BaseModel):
    """Configuration du ducking automatique."""
    enabled: bool = True
    threshold_db: float = Field(default=-20.0, description="Seuil déclenchement (dB)")
    attack_ms: int = Field(default=50, ge=1)
    release_ms: int = Field(default=500, ge=1)
    reduction_db: float = Field(default=-10.0, description="Réduction volume (dB)")


class CompressorConfig(BaseModel):
    """Configuration du compresseur."""
    enabled: bool = True
    threshold_db: float = Field(default=-18.0)
    ratio: float = Field(default=4.0, ge=1.0)
    attack_ms: int = Field(default=5, ge=0)
    release_ms: int = Field(default=100, ge=1)


class LimiterConfig(BaseModel):
    """Configuration du limiteur."""
    enabled: bool = True
    threshold_db: float = Field(default=-1.0)
    release_ms: int = Field(default=100, ge=1)


class AudioMixConfig(BaseModel):
    """Configuration complète du mixage audio."""
    master_target_lufs: float = Field(default=-14.0, description="Cible LUFS (YouTube)")
    voice_volume_db: float = Field(default=0.0, description="Volume voix référence (dB)")
    music_volume_db: float = Field(default=-20.0, description="Volume musique relatif (dB)")
    sfx_volume_db: float = Field(default=-12.0, description="Volume SFX relatif (dB)")
    music_fade_in: float = Field(default=2.0, ge=0.0)
    music_fade_out: float = Field(default=3.0, ge=0.0)
    min_sfx_interval: float = Field(default=5.0, ge=0.0, description="Intervalle min entre SFX (s)")
    avoid_sfx_on_speech: bool = Field(default=True, description="Éviter SFX pendant parole")
    ducking: DuckingConfig = Field(default_factory=DuckingConfig)
    compressor: CompressorConfig = Field(default_factory=CompressorConfig)
    limiter: LimiterConfig = Field(default_factory=LimiterConfig)


class EpidemicSoundConfig(BaseModel):
    """Configuration de l'intégration Epidemic Sound MCP."""
    mcp_url: str = Field(default="https://mcp.epidemicsound.com/api")
    api_key_env: str = Field(default="EPIDEMIC_SOUND_API_KEY")
    search_limit: int = Field(default=20, ge=1, le=100)
    preview_duration: int = Field(default=30, ge=5)
    cache_dir: str = Field(default="/data/audio/cache/epidemic_sound")
    timeout: int = Field(default=30, ge=5)
    retry_max: int = Field(default=3, ge=0)
    default_mood: MusicMood = MusicMood.NEUTRAL
    default_genre: MusicGenre = MusicGenre.ELECTRONIC
    default_tempo_bpm: int = Field(default=120, ge=40, le=200)
    prefer_instrumental: bool = True
    min_duration: int = Field(default=30, ge=10)


class AudioConfig(BaseModel):
    """Configuration complète du module audio."""
    master_volume: float = Field(default=-14.0, description="LUFS cible")
    voice_volume: float = Field(default=0.0, description="dB référence voix")
    music_volume: float = Field(default=-20.0, description="dB musique")
    sfx_volume: float = Field(default=-12.0, description="dB SFX")
    music_fade_in: float = Field(default=2.0, description="secondes")
    music_fade_out: float = Field(default=3.0, description="secondes")
    min_sfx_interval: float = Field(default=5.0, description="secondes")
    avoid_sfx_on_speech: bool = True
    work_dir: str = "/tmp/agent4_cache"
    cc0_library_path: str = "/data/audio/cc0_library"
    epidemic_sound: EpidemicSoundConfig = Field(default_factory=EpidemicSoundConfig)
    mixing: AudioMixConfig = Field(default_factory=AudioMixConfig)


# =============================================================================
# Assets et rapports
# =============================================================================

class AudioAsset(BaseModel):
    """Asset audio préparé (téléchargé, trimé, normalisé)."""
    local_path: Path
    original_id: str
    asset_type: Literal["music", "sfx", "voice"]
    duration: float
    sample_rate: int = 48000
    channels: int = 2
    prep_applied: list[str] = Field(
        default_factory=list,
        description="Préparations appliquées : trim_start, trim_end, gain, fade",
    )


class AudioTrack(BaseModel):
    """Piste audio utilisée dans le montage (contrat de sortie Agent #4 → Agent #5)."""
    type: str = Field(..., description="'music', 'sfx', 'voice', 'ambiance'")
    source: str = Field(..., description="Source : 'epidemic_sound', 'generated', 'original'")
    track_id: str | None = Field(default=None, description="ID Epidemic Sound")
    title: str | None = Field(default=None, description="Titre du morceau")
    start: float = Field(..., description="Début dans le montage (s)")
    end: float = Field(..., description="Fin dans le montage (s)")
    volume_db: float = Field(default=0.0, description="Volume relatif (dB)")
    ducking_applied: bool = Field(default=False)


class AudioMetadata(BaseModel):
    """Métadonnées de la piste audio finale — sortie vers Agent #5.

    Contrat #4 dans DATA_CONTRACTS.md.
    """
    schema_version: str = Field(default="1.0")
    source_edit: str = Field(..., description="Chemin montage source")
    tracks: list[AudioTrack] = Field(..., description="Toutes les pistes audio")
    master_volume_db: float = Field(default=0.0, description="Volume master (dB)")
    peak_level_db: float = Field(..., description="Pic de niveau (dB)")
    rms_level_db: float = Field(..., description="Niveau RMS moyen (dB)")
    loudness_lufs: float = Field(..., description="Loudness intégré (LUFS)")
    music_epidemic_id: str | None = Field(default=None)
    music_bpm: float | None = Field(default=None)
    music_key: str | None = Field(default=None)
    sfx_count: int = Field(default=0, description="Nombre d'effets sonores")

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": "1.0",
                "source_edit": "/data/renders/edit_metadata.json",
                "tracks": [
                    {
                        "type": "voice",
                        "source": "original",
                        "start": 0.0,
                        "end": 60.0,
                        "volume_db": 0.0,
                    },
                    {
                        "type": "music",
                        "source": "epidemic_sound",
                        "track_id": "es_music_789",
                        "title": "Upbeat Electronic",
                        "start": 0.0,
                        "end": 60.0,
                        "volume_db": -20.0,
                        "ducking_applied": True,
                    },
                ],
                "master_volume_db": -14.0,
                "peak_level_db": -0.8,
                "rms_level_db": -17.3,
                "loudness_lufs": -14.1,
                "music_epidemic_id": "es_music_789",
                "music_bpm": 120.0,
                "music_key": "C major",
                "sfx_count": 5,
            }
        }


class AudioReport(BaseModel):
    """Rapport complet d'exécution du pipeline audio.

    Généré à la fin du run pour traçabilité et debugging.
    """
    pipeline_version: str = "4.0.0"
    source_video: str = ""
    source_edit_metadata: str = ""

    # Musique
    music_track: MusicTrack | None = None
    music_duration: float = 0.0
    music_looped: bool = False

    # Effets sonores
    sfx_placed: int = 0
    sfx_list: list[SoundPlacement] = Field(default_factory=list)
    sfx_epidemic_count: int = 0
    sfx_cc0_count: int = 0

    # Analyse narrative
    beats_detected: int = 0
    beats_list: list[NarrativeBeat] = Field(default_factory=list)

    # Mixage
    master_lufs: float = 0.0
    peak_db: float = 0.0
    rms_db: float = 0.0
    ducking_applied: bool = False
    compressor_applied: bool = False

    # Fichiers de sortie
    video_output: str = ""
    audio_master: str = ""
    audio_metadata: str = ""

    # Métriques
    total_duration: float = 0.0
    processing_time_ms: float = 0.0
    epidemic_api_calls: int = 0
    cc0_fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Contrat d'entrée : EditMetadata (Agent #3 → Agent #4)
# =============================================================================

class EditSegmentTiming(BaseModel):
    """Timing d'un segment dans le montage final."""
    montage_start: float = Field(..., description="Début dans le montage final (s)")
    montage_end: float = Field(..., description="Fin dans le montage final (s)")
    original_start: float = Field(..., description="Début dans la vidéo brute (s)")
    original_end: float = Field(..., description="Fin dans la vidéo brute (s)")
    text: str = Field(..., description="Texte du segment")


class EditMetadata(BaseModel):
    """Métadonnées de la version montée — entrée Agent #4."""
    schema_version: str = Field(default="1.0")
    source_cutlist: str = Field(..., description="Chemin fichier cutlist source")
    total_duration: float = Field(..., description="Durée totale du montage (s)")
    segments: list[EditSegmentTiming] = Field(
        ..., description="Timing de chaque segment dans le montage"
    )
    pace: str = Field(..., description="'slow', 'medium', 'fast'")
    beat_per_minute_estimate: float | None = Field(default=None)
    scene_changes: list[float] = Field(default_factory=list, description="Timecodes changements scène (s)")
    dominant_colors: list[str] | None = Field(default=None)
    mood: str | None = Field(default=None, description="'energetic', 'calm', 'dramatic', 'professional'")
    speech_segments: list[dict] = Field(
        default_factory=list,
        description="[{start, end, text}] pour ducking parole/musique"
    )
