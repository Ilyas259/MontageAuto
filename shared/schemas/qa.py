"""
Schémas Pydantic — Qualité & Feedback (Agent #5 + Agent #6)
Version: 1.0.0
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from decimal import Decimal


class MetricScore(BaseModel):
    """Score d'une métrique de qualité spécifique."""
    metric_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    details: Optional[str] = None


class QualityIssue(BaseModel):
    """Problème de qualité détecté par Gemini ou la review humaine."""
    timestamp: Optional[Decimal] = None
    severity: Literal["critical", "major", "minor", "suggestion"] = "minor"
    category: Literal[
        "cut", "audio", "visual", "timing", "b_roll", "subtitle",
        "transition", "pacing", "narrative", "other"
    ]
    description: str
    suggestion: Optional[str] = None
    source: Literal["gemini", "human"] = "gemini"


class QaReport(BaseModel):
    """
    Rapport de qualité complet (sortie Agent #5 → Agent #6).
    
    ATTENTION : Tous les scores sont sur une échelle de 0.0 à 1.0.
    - 0.0 = qualité nulle
    - 0.5 = acceptable
    - 0.7 = bon
    - 0.95 = excellent
    """
    schema_version: str = "1.0.0"
    overall_score: float = Field(..., ge=0.0, le=1.0)
    metrics: List[MetricScore]
    issues: List[QualityIssue]
    feedback_text: str = Field(..., max_length=5000)
    iteration: int = Field(default=0, ge=0)
    analysis_mode: Literal["keyframes", "full_video", "spot_check"] = "keyframes"
    video_duration_s: Decimal
    frames_analyzed: int
    cost_estimate_usd: Optional[float] = None

    @property
    def is_approved(self) -> bool:
        """Auto-approbation si score >= 0.8 et pas d'issues critical/major."""
        if self.overall_score < 0.8:
            return False
        critical_or_major = [
            i for i in self.issues
            if i.severity in ("critical", "major")
        ]
        return len(critical_or_major) == 0


class FeedbackInstructions(BaseModel):
    """Instructions de feedback pour les agents génératifs (sortie Agent #5 → Agents #2, #3, #4)."""
    schema_version: str = "1.0.0"
    target_agent: Literal["agent2", "agent3", "agent4"]
    issues_to_fix: List[QualityIssue]
    priority_change: Optional[Literal["increase", "decrease", "none"]] = None
    suggested_config_change: Optional[dict] = None


class HumanApproval(BaseModel):
    """Validation humaine finale (Agent #6)."""
    schema_version: str = "1.0.0"
    approved: bool
    reviewer: str
    comments: Optional[str] = None
    changes_requested: Optional[List[str]] = None
    approval_timestamp: str

    class Config:
        frozen = True
