"""
Module de preview rapide — génère une version basse résolution pour validation humaine.

Stratégie de preview :
1. Extraire les segments en basse résolution (scale=640:360)
2. Appliquer les templates simplifiés (pas d'animations complexes)
3. Sous-titres optionnels (burn-in rapide)
4. Concaténer le tout

Idéal pour :
- Valider le rythme du montage avant le rendu final
- Tester les transitions
- Vérifier la synchro labiale
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from agent3_montage.config import MontageConfig
from agent3_montage.ffmpeg_ops import FFmpegError, FFmpegOps
from agent3_montage.models import ComposedSegment
from agent3_montage.subtitles import SubtitleEngine

logger = logging.getLogger(__name__)


class PreviewGenerator:
    """
    Génère une preview rapide à partir des segments composés.

    2x plus rapide que le rendu final :
    - Résolution réduite (640x360 par défaut)
    - Preset ultrafast
    - Pas d'animations complexes
    - Sous-titres simplifiés
    """

    def __init__(self, config: MontageConfig):
        self.config = config
        self.preview_config = config.model_copy()
        self.preview_config.preview_scale = 0.5
        # Override output resolution pour la preview
        w, h = config.output_size
        self.preview_resolution = (w // 2, h // 2) if w > 1280 else (w, h)

    async def generate(
        self,
        segments: list[ComposedSegment],
        output_path: Path,
        renderer: Any,  # AbstractRenderer
    ) -> Path:
        """
        Génère une preview vidéo.

        Méthode 1 (optimale) : Utiliser le renderer disponible avec config preview
        Méthode 2 (fallback) : FFmpeg direct avec segments extraits
        """
        from agent3_montage.renderers.base import CompositionConfig

        # Préparer une composition en mode preview
        composition = CompositionConfig(
            template=segments[0].template if segments else None,
            segments=segments,
            subtitles={},
            config=self.preview_config,
            output_path=output_path,
            mode="preview",
        )

        try:
            return await renderer.render_preview(composition)
        except Exception as e:
            logger.warning(f"Renderer preview failed, using FFmpeg fallback: {e}")
            return await self._ffmpeg_fallback(segments, output_path)

    async def _ffmpeg_fallback(
        self,
        segments: list[ComposedSegment],
        output_path: Path,
    ) -> Path:
        """Fallback preview via FFmpeg direct."""
        temp_dir = output_path.parent / "_preview_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        segment_clips = []

        for i, seg in enumerate(segments):
            out = temp_dir / f"prev_seg_{i:04d}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(seg.source_clip),
                "-vf", f"scale={self.preview_resolution[0]}:{self.preview_resolution[1]}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "96k",
                str(out),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            segment_clips.append(out)

        # Concaténer
        concat_out = await FFmpegOps.concat_simple(segment_clips, output_path)
        return concat_out
