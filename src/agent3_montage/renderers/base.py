"""
Interface abstraite pour les renderers vidéo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from agent3_montage.config import MontageConfig
from agent3_montage.models import ComposedSegment, CompositionTemplate


class CompositionConfig(BaseModel):
    """Configuration complète pour un rendu de composition."""
    template: CompositionTemplate
    segments: list[ComposedSegment]
    subtitles: dict
    config: MontageConfig
    output_path: Path
    mode: str = "final"  # "preview" | "final"


class AbstractRenderer(ABC):
    """Interface commune pour tous les renderers."""

    @abstractmethod
    async def render(self, composition: CompositionConfig) -> Path:
        """Rend la composition complète."""
        ...

    @abstractmethod
    async def render_preview(self, composition: CompositionConfig) -> Path:
        """Rend une preview rapide."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Vérifie si le renderer est disponible sur ce système."""
        ...

    @abstractmethod
    async def get_version(self) -> str:
        """Retourne la version du renderer."""
        ...

    @abstractmethod
    async def get_name(self) -> str:
        """Retourne le nom du renderer."""
        ...
