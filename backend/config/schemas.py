"""Modèles Pydantic pour la configuration des agents du pipeline."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class LayerConfig(BaseModel):
    """Une couche de configuration (DEFAULTS, PROFIL, USER, RUN)."""
    agents: dict[str, dict[str, Any]] = Field(default_factory=dict)
    profile: str = "natural"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration d'un agent dans le pipeline."""
    id: str
    name: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[int] = None  # minutes
    mode: str = Field(default="auto", description="local|api|auto")


class PipelineConfig(BaseModel):
    """Configuration complète d'un pipeline."""
    agents: list[AgentConfig] = Field(default_factory=list)
    profile: str = "natural"
    mode: str = Field(default="api", description="Valeur par défaut pour tous les agents")
    run_params: Optional[dict[str, Any]] = None


class ResolvedConfig(BaseModel):
    """Configuration finale après merge des 4 couches."""
    agents: dict[str, dict[str, Any]] = Field(default_factory=dict)
    profile: str = "natural"
    mode: str = "api"
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ValidationError(BaseModel):
    """Erreur de validation de configuration."""
    field: str
    message: str
    value: Any = None
    expected: str = ""


class ValidationResult(BaseModel):
    """Résultat de validation."""
    valid: bool = True
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
