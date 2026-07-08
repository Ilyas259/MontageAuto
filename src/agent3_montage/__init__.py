"""
Agent #3 — Montage & Animation
Module d'assemblage vidéo automatisé.
Pipeline : découpage source → composition (facecam/split/full-broll) → B-roll → sous-titres → rendu.
"""

__version__ = "3.0.0"
__all__ = [
    "MontagePipeline",
    "MontageConfig",
    "TemplateEngine",
    "BrollPlacer",
    "SubtitleEngine",
    "FFmpegOps",
    "RendererFactory",
    "QualityLoop",
]

from agent3_montage.orchestrator import MontagePipeline
from agent3_montage.config import MontageConfig
from agent3_montage.template_engine import TemplateEngine
from agent3_montage.broll_placer import BrollPlacer
from agent3_montage.subtitles import SubtitleEngine
from agent3_montage.ffmpeg_ops import FFmpegOps
from agent3_montage.renderers import RendererFactory
from agent3_montage.quality_loop import QualityLoop
