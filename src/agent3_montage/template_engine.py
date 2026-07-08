"""
Moteur de templates — résout et applique le template approprié à chaque segment.
"""

from __future__ import annotations

import copy
from typing import Any

from agent3_montage.config import MontageConfig
from agent3_montage.models import CompositionTemplate, CutSegment
from agent3_montage.templates.facecam import FACECAM_DEFAULT
from agent3_montage.templates.split import SPLIT_50_50
from agent3_montage.templates.full_broll import FULL_BROLL_DEFAULT
from agent3_montage.templates.transitions import TRANSITION_CUT


class TemplateEngine:
    """Moteur qui résout et applique les templates aux segments."""

    _registry: dict[str, CompositionTemplate] = {}

    @classmethod
    def register(cls, template: CompositionTemplate) -> None:
        """Enregistre un template dans le registre global."""
        cls._registry[template.name] = template

    @classmethod
    def get(cls, name: str) -> CompositionTemplate | None:
        """Récupère un template par son nom."""
        return cls._registry.get(name)

    @classmethod
    def list_templates(cls) -> list[CompositionTemplate]:
        """Retourne tous les templates enregistrés."""
        return list(cls._registry.values())

    @classmethod
    def list_by_type(cls, t: str) -> list[CompositionTemplate]:
        """Retourne les templates d'un type donné."""
        return [tmpl for tmpl in cls._registry.values() if tmpl.type == t]

    @classmethod
    def resolve(
        cls,
        segment: CutSegment,
        config: MontageConfig,
    ) -> CompositionTemplate:
        """Sélectionne et personnalise le template approprié pour un segment."""
        base = cls._get_default_for_type(segment.type)

        if segment.type == "facecam":
            return cls._apply_facecam_position(base, config)
        elif segment.type == "split":
            return cls._adjust_split_ratio(base, segment)
        elif segment.type == "full_broll":
            return base
        elif segment.type == "transition":
            return cls._resolve_transition(segment, config)

        return base

    @classmethod
    def _get_default_for_type(cls, seg_type: str) -> CompositionTemplate:
        """Retourne le template par défaut pour un type de segment."""
        mapping = {
            "facecam": FACECAM_DEFAULT,
            "split": SPLIT_50_50,
            "full_broll": FULL_BROLL_DEFAULT,
            "transition": TRANSITION_CUT,
        }
        base = mapping.get(seg_type, FACECAM_DEFAULT)
        return copy.deepcopy(base)

    @staticmethod
    def _apply_facecam_position(
        template: CompositionTemplate,
        config: MontageConfig,
    ) -> CompositionTemplate:
        """Ajuste la position et taille du speaker selon la configuration."""
        size = config.facecam_size
        margin = 0.02  # 2% margin from edges

        positions = {
            "bottom-right": (1.0 - size - margin, 1.0 - size * (9 / 16) - margin),
            "bottom-left": (margin, 1.0 - size * (9 / 16) - margin),
            "top-right": (1.0 - size - margin, margin),
            "top-left": (margin, margin),
        }

        x, y = positions.get(config.facecam_position, positions["bottom-right"])
        template.layout["speaker"]["x"] = x
        template.layout["speaker"]["y"] = y
        template.layout["speaker"]["w"] = size
        template.layout["speaker"]["h"] = size * (9 / 16)  # 16:9 aspect ratio

        if config.facecam_corner_radius:
            template.layout["speaker"]["border_radius"] = config.facecam_corner_radius
        if config.facecam_shadow:
            template.layout["speaker"]["box_shadow"] = "0 4px 20px rgba(0,0,0,0.4)"

        return template

    @staticmethod
    def _adjust_split_ratio(
        template: CompositionTemplate,
        segment: CutSegment,
    ) -> CompositionTemplate:
        """Ajuste le ratio du split screen si le segment a des B-rolls prioritaires."""
        if not segment.brolls:
            return template

        # Si un B-roll split a priorité haute, favoriser le visuel
        high_prio = any(
            b.priority >= 8 for b in segment.brolls if b.placement == "split"
        )
        if high_prio:
            template.layout["speaker"]["w"] = 0.3
            template.layout["broll"]["w"] = 0.7
            template.layout["broll"]["x"] = 0.3

        return template

    @staticmethod
    def _resolve_transition(
        segment: CutSegment,
        config: MontageConfig,
    ) -> CompositionTemplate:
        """Sélectionne le template de transition approprié."""
        trans_type = segment.transition_out or config.transition_default

        mapping = {
            "cut": "transition_cut",
            "fade": "transition_fade",
            "slide": "transition_slide",
            "zoom": "transition_zoom",
        }

        name = mapping.get(trans_type, "transition_cut")
        base = TemplateEngine._registry.get(name)
        if base:
            base = copy.deepcopy(base)
            base.default_duration = config.transition_duration
            if "duration" in base.animation:
                base.animation["duration"] = config.transition_duration
            return base

        return copy.deepcopy(TRANSITION_CUT)
