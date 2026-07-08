"""
Schémas Pydantic centralisés — Video Automation Pipeline

Tous les agents importent depuis ce module central pour éviter
les divergences de schémas. Versionné via schema_version.
"""

from .transcript import (
    Transcript, Word, Sentence, SpeakerSegment, VADSegment,
    TranscriptConfig, TranscriptionOutput, TranscriptionMetadata
)
from .cutlist import (
    ErrorDetection, KeptSegment, RemovedSegment,
    BRollSuggestion, CutList, CleanScript
)
from .audio import (
    SoundEffect, MusicTrack, AudioMix, AudioConfig,
    AudioMetadata, DuckingConfig
)
from .qa import (
    QaReport, QualityIssue, MetricScore,
    FeedbackInstructions, HumanApproval
)

__all__ = [
    "Transcript", "Word", "Sentence", "SpeakerSegment", "VADSegment",
    "TranscriptConfig", "TranscriptionOutput", "TranscriptionMetadata",
    "ErrorDetection", "KeptSegment", "RemovedSegment",
    "BRollSuggestion", "CutList", "CleanScript",
    "SoundEffect", "MusicTrack", "AudioMix", "AudioConfig",
    "AudioMetadata", "DuckingConfig",
    "QaReport", "QualityIssue", "MetricScore",
    "FeedbackInstructions", "HumanApproval",
]

SCHEMA_VERSION = "1.0.0"
