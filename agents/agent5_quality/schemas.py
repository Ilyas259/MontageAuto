"""
Agent #5 — Boucle Qualité & Auto-Amélioration
Schémas Pydantic pour les feedbacks, rapports de qualité et corrections.

Utilisation :
    from agents.agent5_quality.schemas import (
        QualityReport, FeedbackItem, CorrectionRequest,
        IterationResult, Severity, FeedbackCategory, TargetAgent
    )
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# Énumérations
# =============================================================================

class Severity(str, Enum):
    """Sévérité d'un problème détecté."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackCategory(str, Enum):
    """Catégorie d'un feedback qualité."""
    RYTHME = "rythme"
    CLARTE = "clarte"
    TRANSITION = "transition"
    BROLL = "b_roll"
    AUDIO_SYNC = "audio_sync"
    COUPURE = "coupure"
    COHERENCE = "coherence"
    AUTRE = "autre"


class TargetAgent(str, Enum):
    """Agent cible d'une correction."""
    AGENT1_TRANSCRIPTION = "agent1_transcription"
    AGENT2_DERUSHAGE = "agent2_derushage"
    AGENT3_MONTAGE = "agent3_montage"
    AGENT4_AUDIO = "agent4_audio"
    AGENT5_QUALITY = "agent5_quality"


class FeedbackSeverityMode(str, Enum):
    """Mode de sévérité globale du feedback."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisMode(str, Enum):
    """Mode d'analyse vidéo."""
    FULL_VIDEO = "full_video"
    KEYFRAMES = "keyframes"
    TEXTUAL = "textual"


class StopReason(str, Enum):
    """Raison d'arrêt de la boucle qualité."""
    QUALITY_MET = "quality_met"
    MAX_ITERATIONS = "max_iterations"
    STAGNANT_CONVERGENCE = "stagnant_convergence"
    REGRESSION = "regression"
    ERROR = "error"
    MANUAL_OVERRIDE = "manual_override"
    DISABLED = "disabled"


# =============================================================================
# Modèles de feedback
# =============================================================================

class FeedbackItem(BaseModel):
    """Un élément de feedback individuel détecté par Gemini.

    Attributes:
        category: Catégorie du problème.
        severity: Sévérité (low/medium/high/critical).
        timestamp: Timestamp dans la vidéo (format "HH:MM:SS").
        description: Description claire du problème.
        suggestion: Suggestion de correction actionnable.
        target_agent: Agent qui doit appliquer la correction.
        auto_fixable: True si correction automatique possible.
        confidence: Niveau de confiance de la détection (0.0 - 1.0).
    """
    category: FeedbackCategory
    severity: Severity
    timestamp: Optional[str] = Field(
        default=None,
        pattern=r'^\d{2}:\d{2}:\d{2}(\.\d+)?$',
        description="Timestamp dans la vidéo (format HH:MM:SS[.mmm])"
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Description du problème détecté"
    )
    suggestion: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Suggestion de correction actionnable"
    )
    target_agent: TargetAgent
    auto_fixable: bool = False
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confiance (0.0 = incertain, 1.0 = certain)"
    )


# =============================================================================
# Rapports de qualité
# =============================================================================

class QualityReport(BaseModel):
    """Rapport de qualité complet produit par Gemini après analyse.

    Attributes:
        iteration: Numéro d'itération (0 = analyse initiale).
        timestamp: Horodatage de l'analyse.
        video_path: Chemin de la vidéo analysée.
        video_duration_seconds: Durée de la vidéo en secondes.
        criteria_scores: Score par critère d'évaluation (0.0 - 1.0).
        overall_score: Score global pondéré (0.0 - 1.0).
        issues: Liste des problèmes détectés.
        positives: Points positifs / renforcements.
        analysis_mode: Mode d'analyse utilisé.
        frames_analyzed: Nombre de frames analysées.
        gemini_model: Modèle Gemini utilisé.
        token_usage: Statistiques de tokens (prompt/completion).
        passed: True si overall_score >= min_score configuré.
    """
    iteration: int = Field(default=0, ge=0, description="Numéro d'itération")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    video_path: str
    video_duration_seconds: float = Field(..., gt=0)

    criteria_scores: dict[FeedbackCategory, float] = Field(
        ...,
        description="Score par critère (0.0 - 1.0)"
    )
    overall_score: float = Field(..., ge=0.0, le=1.0)

    issues: list[FeedbackItem] = Field(default_factory=list)
    positives: list[str] = Field(default_factory=list)

    analysis_mode: AnalysisMode = AnalysisMode.KEYFRAMES
    frames_analyzed: int = Field(default=0, ge=0)
    gemini_model: str = "gemini-2.5-pro"
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0}
    )

    passed: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "iteration": 1,
                "video_path": "/output/final_v1.mp4",
                "video_duration_seconds": 185.0,
                "criteria_scores": {
                    "rythme": 0.65,
                    "clarte": 0.80,
                    "transition": 0.70,
                    "b_roll": 0.55,
                    "audio_sync": 0.90,
                    "coupure": 0.75,
                    "coherence": 0.85
                },
                "overall_score": 0.72,
                "issues": [],
                "positives": ["Le rythme général est bon"],
                "analysis_mode": "keyframes",
                "frames_analyzed": 12,
                "gemini_model": "gemini-2.5-pro",
                "token_usage": {"prompt_tokens": 4500, "completion_tokens": 1200},
                "passed": True
            }
        }


# =============================================================================
# Corrections
# =============================================================================

class CorrectionRequest(BaseModel):
    """Requête de correction envoyée à un agent cible.

    Attributes:
        report_id: Identifiant du rapport source.
        iteration: Itération courante.
        target_agent: Agent qui doit exécuter la correction.
        priority: Priorité de la correction.
        items: Liste des feedbacks à corriger.
        context: Contexte additionnel (chemins, métadonnées).
        gemini_instruction: Instruction directe de Gemini (override flag).
    """
    report_id: str
    iteration: int = Field(..., ge=0)
    target_agent: TargetAgent
    priority: Literal["urgent", "high", "medium", "low"]
    items: list[FeedbackItem] = Field(..., min_length=1)
    context: dict = Field(default_factory=dict)
    gemini_override: bool = Field(
        default=True,
        description="Si True, l'agent cible DOIT exécuter ce feedback (override)"
    )


# =============================================================================
# Mémoire d'apprentissage
# =============================================================================

class QualityMemory(BaseModel):
    """Enregistrement d'une itération pour apprentissage futur.

    Attributes:
        iteration: Numéro d'itération.
        video_hash: Hash du contenu vidéo (SHA256).
        report: Rapport de qualité complet.
        corrections_applied: Corrections qui ont été appliquées.
        score_before: Score avant correction.
        score_after: Score après correction (None si pas encore analysé).
        pattern_signature: Hash du pattern de défauts (regroupement).
    """
    iteration: int = Field(..., ge=0)
    video_hash: str
    report: QualityReport
    corrections_applied: list[FeedbackItem] = Field(default_factory=list)
    score_before: float = Field(..., ge=0.0, le=1.0)
    score_after: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    pattern_signature: Optional[str] = None


# =============================================================================
# Résultat de la boucle
# =============================================================================

class IterationResult(BaseModel):
    """Résultat complet de la boucle qualité après N itérations.

    Attributes:
        success: True si le score final >= min_score.
        final_iteration: Nombre d'itérations effectuées.
        final_score: Score final obtenu.
        improvement: Amélioration du score (final - initial).
        total_issues_found: Nombre total de problèmes détectés.
        total_issues_fixed: Nombre total de problèmes corrigés.
        corrections_applied: Liste de toutes les corrections envoyées.
        history: Historique complet des rapports d'analyse.
        stopped_reason: Raison de l'arrêt de la boucle.
        duration_seconds: Durée totale de la boucle.
        token_usage_total: Tokens totaux consommés.
    """
    success: bool
    final_iteration: int = Field(..., ge=0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    improvement: float = Field(default=0.0)

    total_issues_found: int = Field(default=0, ge=0)
    total_issues_fixed: int = Field(default=0, ge=0)
    corrections_applied: list[CorrectionRequest] = Field(default_factory=list)

    history: list[QualityReport] = Field(default_factory=list)
    stopped_reason: StopReason
    duration_seconds: float = Field(default=0.0, ge=0.0)
    token_usage_total: dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0}
    )

    def improvement_percent(self) -> float:
        """Retourne l'amélioration en pourcentage."""
        if self.final_score == 0.0:
            return 0.0
        return round(self.improvement * 100, 1)


# =============================================================================
# Métriques de monitoring
# =============================================================================

class QualityMetrics(BaseModel):
    """Métriques exposées pour le monitoring du pipeline."""
    session_id: str
    iterations_count: int
    total_duration_seconds: float
    final_score: float
    score_improvement: float
    total_tokens: int
    total_cost_usd: float
    gemini_calls: int
    auto_fixes_applied: int
    human_interventions: int
    stopped_reason: str


# =============================================================================
# Configuration du module
# =============================================================================

class QualityConfig(BaseModel):
    """Configuration externalisée du module qualité."""
    # Seuils
    min_score: float = Field(default=0.7, ge=0.0, le=1.0)
    max_iterations: int = Field(default=3, ge=1, le=10)
    feedback_severity: FeedbackSeverityMode = FeedbackSeverityMode.MEDIUM

    # Analyse
    analyze_every_n_frames: int = Field(default=30, ge=1)
    max_frames_per_analysis: int = Field(default=100, ge=1)
    analysis_mode: AnalysisMode = AnalysisMode.KEYFRAMES
    video_max_duration_minutes: int = Field(default=30, ge=1)

    # Corrections
    auto_fix_minor: bool = True
    auto_fix_categories: list[FeedbackCategory] = Field(
        default_factory=lambda: [
            FeedbackCategory.BROLL,
            FeedbackCategory.COUPURE,
            FeedbackCategory.TRANSITION,
        ]
    )

    # Gemini
    gemini_model: str = "gemini-2.5-pro"
    gemini_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    gemini_max_tokens: int = Field(default=8192, ge=1)
    gemini_api_timeout: int = Field(default=60, ge=1)

    # Boucle
    strict_convergence: bool = True
    render_timeout: int = Field(default=300, ge=1)
    rollback_on_regression: bool = True
    tolerance: float = Field(
        default=0.02,
        ge=0.0,
        le=0.1,
        description="Tolérance sous le min_score pour valider quand max_iterations atteint"
    )

    # Logging
    log_each_iteration: bool = True
    save_frames_analyzed: bool = False
    keep_iteration_artifacts: bool = True
    memory_size: int = Field(default=100, ge=0)

    # Activation
    enabled: bool = True
