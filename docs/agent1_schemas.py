"""
Agent #1 — Acquisition & Transcription
Schémas Pydantic v2.7+ — Entrées, Sorties et Modèles Intermédiaires

Ces schémas définissent le contrat de données complet de l'Agent #1 :
- Entrée : AudioInput (fichier vidéo brut)
- Intermédiaires : ScribeResult, WhisperXResult, VADResult
- Sortie finale : Transcript (transcript.json)
"""

from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Optional, Literal
from datetime import datetime


# =============================================================================
# AUDIO — Entrée et informations audio
# =============================================================================

class AudioInfo(BaseModel):
    """Informations sur le fichier audio extrait depuis la vidéo brute."""
    file_path: Path
    sample_rate: int = 16000
    channels: int = 1
    duration_seconds: float
    bit_depth: int = 16


class AudioInput(BaseModel):
    """Entrée du pipeline — fichier vidéo brut à transcrire."""
    video_path: Path
    audio_output_dir: Path = Path("./cache/audio")
    language: str = "fr"
    whisperx_model: Literal["tiny", "base"] = "tiny"
    force_reprocess: bool = False


# =============================================================================
# SCRIBE V2 — Résultat de l'API ElevenLabs Scribe
# =============================================================================

class ScribeWord(BaseModel):
    """Mot individuel transcrit par Scribe V2."""
    text: str
    start: float
    end: float
    confidence: float = Field(ge=0.0, le=1.0)
    speaker_id: Optional[str] = None


class ScribeSegment(BaseModel):
    """Segment de phrase transcrit par Scribe V2 (avec ponctuation)."""
    text: str
    start: float
    end: float
    words: List[ScribeWord]
    speaker_id: Optional[str] = None
    language: str = "fr"


class ScribeResult(BaseModel):
    """Résultat complet de l'API ElevenLabs Scribe V2."""
    segments: List[ScribeSegment]
    full_text: str
    language: str = "fr"
    language_confidence: float = Field(ge=0.0, le=1.0)
    processing_time_ms: Optional[int] = None
    api_call_id: Optional[str] = None
    cached: bool = False


# =============================================================================
# WHISPERX — Résultat de la transcription locale WhisperX
# =============================================================================

class WhisperXWord(BaseModel):
    """Mot individuel aligné temporellement par WhisperX."""
    text: str
    start: float
    end: float
    confidence: float = Field(ge=0.0, le=1.0)
    speaker_id: Optional[str] = None


class WhisperXSilence(BaseModel):
    """Segment de silence détecté par WhisperX (écart entre segments)."""
    start: float
    end: float
    duration_seconds: float


class WhisperXSegment(BaseModel):
    """Segment de parole détecté par WhisperX."""
    text: str
    start: float
    end: float
    words: List[WhisperXWord]
    speaker_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class WhisperXResult(BaseModel):
    """Résultat complet de WhisperX (local, CPU)."""
    segments: List[WhisperXSegment]
    word_segments: List[WhisperXWord]
    silences: List[WhisperXSilence]
    language: str = "fr"
    model_name: str = "tiny"
    processing_time_seconds: float
    speakers_detected: int = 1


# =============================================================================
# VAD — Résultat du détecteur de silence Silero VAD
# =============================================================================

class VADSegment(BaseModel):
    """Segment unitaire VAD : parole ou silence."""
    start: float
    end: float
    is_speech: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VADResult(BaseModel):
    """Résultat complet du détecteur Silero VAD."""
    segments: List[VADSegment]
    sample_rate: int = 16000
    frame_duration_ms: int = 30
    processing_time_ms: float
    silence_segments: List[VADSegment]
    speech_segments: List[VADSegment]


# =============================================================================
# TRANSCRIPT — Sortie finale (transcript.json)
# =============================================================================

class Word(BaseModel):
    """Mot individuel dans la sortie finale du transcript."""
    text: str
    start: float
    end: float
    confidence: float = Field(ge=0.0, le=1.0)
    speaker_id: Optional[str] = None
    source: Literal["scribe", "whisperx", "fused"] = "fused"


class Silence(BaseModel):
    """Segment de silence dans la sortie finale du transcript."""
    start: float
    end: float
    duration_seconds: float
    source: Literal["whisperx", "vad", "fused"] = "fused"
    confidence: float = Field(ge=0.0, le=1.0)


class Sentence(BaseModel):
    """Phrase complète (reconstituée) avec ponctuation."""
    text: str
    start: float
    end: float
    words: List[Word]
    speaker_id: Optional[str] = None


class SpeakerInfo(BaseModel):
    """Information sur un locuteur identifié."""
    speaker_id: str = "SPEAKER_00"
    total_words: int = 0
    total_duration_seconds: float = 0.0
    segment_count: int = 0


class Transcript(BaseModel):
    """
    Sortie finale de l'Agent #1 — écrite dans /output/transcript.json.
    
    Contrat pour l'Agent #2 (Dérushage) :
    - words[] : mots avec timestamps précis
    - silences[] : segments de silence timecodés
    - sentences[] : phrases reconstituées
    - speakers[] : locuteurs identifiés
    """
    # Métadonnées
    video_filename: str
    duration_seconds: float
    language: str = "fr"
    processing_timestamp: datetime = Field(default_factory=datetime.now)
    agent_version: str = "1.0.0"
    
    # Corpus principal
    words: List[Word] = Field(default_factory=list)
    silences: List[Silence] = Field(default_factory=list)
    sentences: List[Sentence] = Field(default_factory=list)
    speakers: List[SpeakerInfo] = Field(default_factory=list)
    
    # Métriques de qualité
    total_words: int = 0
    total_silences: int = 0
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_seconds: float = 0.0

    model_config = {"extra": "forbid"}
