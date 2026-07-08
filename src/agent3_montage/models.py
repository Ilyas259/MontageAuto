"""
Modèles de données Pydantic pour le pipeline de montage.
Définit les contrats entre Agent #2 (entrée), Agent #3 (interne), Agent #5 (sortie).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Modèles d'entrée (depuis Agent #2 — cut_list.json)
# ═══════════════════════════════════════════════════════════

class BrollPlacement(BaseModel):
    """Suggestion de B-roll venant de l'Agent #2 — placement dans la timeline."""
    start_time: float
    end_time: float
    concept: str
    placement: Literal["overlay", "fullscreen", "split"]
    priority: int = 5
    source: Literal["generated", "stock", "library", "none"] = "generated"
    asset_path: str | None = None


class CutSegment(BaseModel):
    """Segment vidéo à conserver dans le montage final."""
    id: str
    start_time: float
    end_time: float
    type: Literal["facecam", "split", "full_broll", "transition"]
    transcript: str
    brolls: list[BrollPlacement] = []
    transition_out: Literal["cut", "fade", "slide", "zoom"] = "cut"


class CutList(BaseModel):
    """Contrat d'entrée principal depuis l'Agent #2."""
    segments: list[CutSegment]
    broll_suggestions: list[BrollPlacement]
    metadata: dict = {}


# ═══════════════════════════════════════════════════════════
# Modèles de composition (internes)
# ═══════════════════════════════════════════════════════════

class CompositionTemplate(BaseModel):
    """Template de composition pour un segment — layout + animations."""
    name: str
    type: Literal["facecam", "split", "full_broll", "transition"]
    layout: dict = {}
    animation: dict = {}
    default_duration: float = 5.0
    subtitle_position: Literal["bottom", "top", "center"] = "bottom"


class ComposedSegment(BaseModel):
    """Segment après assignation d'un template et placement B-roll."""
    segment_id: str
    template: CompositionTemplate
    source_clip: Path
    broll_clips: list[Path] = []
    broll_placements: list[BrollPlacement] = []
    subtitle_events: list[SubtitleEvent] = []
    output_path: Path | None = None


# ═══════════════════════════════════════════════════════════
# Sous-titres
# ═══════════════════════════════════════════════════════════

class SubtitleEvent(BaseModel):
    """Un mot ou groupe de mots à afficher à l'écran."""
    text: str
    start_time: float
    end_time: float
    word_index: int = 0
    is_highlighted: bool = False


class SubtitleConfig(BaseModel):
    """Configuration du rendu des sous-titres."""
    style: Literal["karaoke", "block", "none"] = "block"
    font: str = "Inter"
    font_size: int = 28
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    position: Literal["bottom", "top", "center"] = "bottom"
    margin_bottom: int = 60
    max_width_pct: float = 0.85
    line_height: float = 1.4
    karaoke_highlight_color: str = "#FFD700"
    karaoke_advance_mode: Literal["word", "char"] = "word"


# ═══════════════════════════════════════════════════════════
# Rapport de montage (sortie vers Agent #5)
# ═══════════════════════════════════════════════════════════

class SegmentRenderInfo(BaseModel):
    """Information de rendu pour un segment individuel."""
    segment_id: str
    source_range: tuple[float, float]
    template_type: str
    duration: float
    brolls_applied: int
    render_success: bool
    render_duration_ms: float
    output_path: str
    errors: list[str] = []


class MontageReport(BaseModel):
    """Rapport complet de l'exécution du pipeline de montage."""
    pipeline_version: str = "3.0.0"
    source_video: str
    total_segments: int
    total_duration: float
    segments: list[SegmentRenderInfo] = []
    brolls_total: int = 0
    brolls_placed: int = 0
    transitions_applied: list[str] = []
    subtitle_style: str = "block"
    render_mode: str = "final"
    total_render_time_ms: float = 0.0
    output_path: str = ""
    preview_path: str | None = None
    quality_feedback: list[dict] = []
    errors: list[str] = []


# ═══════════════════════════════════════════════════════════
# Boucle qualité (Agent #5)
# ═══════════════════════════════════════════════════════════

class QualityIssue(BaseModel):
    """Un problème détecté par l'Agent #5."""
    severity: Literal["critical", "major", "minor", "suggestion"]
    category: str
    description: str
    segment_id: str | None = None
    suggested_action: str | None = None


class SegmentFeedback(BaseModel):
    """Feedback par segment de l'Agent #5."""
    segment_id: str
    score: float = Field(ge=0, le=10)
    issues: list[str] = []
    suggested_template: str | None = None


class QualityFeedback(BaseModel):
    """Feedback complet de l'Agent #5 (Gemini)."""
    iteration: int = 1
    overall_score: float = Field(ge=0, le=10)
    segments_scores: list[SegmentFeedback] = []
    issues: list[QualityIssue] = []
    suggestions: list[str] = []
    auto_fix: bool = False


class Correction(BaseModel):
    """Correction à appliquer suite au feedback."""
    type: Literal["config", "segment", "pipeline"]
    key: str | None = None
    value: str | float | bool | None = None
    action: str | None = None
    segment_id: str | None = None


# ═══════════════════════════════════════════════════════════
# Sync audio
# ═══════════════════════════════════════════════════════════

class SyncReport(BaseModel):
    """Rapport de vérification de synchronisation labiale."""
    synced: bool
    offset_ms: float
    audio_stream_index: int = 0
    video_stream_index: int = 0
