"""
Fabrique de renderers — détecte le renderer disponible et retourne l'instance appropriée.

Hiérarchie de fallback :
1. Hyperframes (canonique, payant)
2. Remotion (open source)
3. FFmpeg-only (fallback ultime)
"""

from __future__ import annotations

import logging

from agent3_montage.renderers.base import AbstractRenderer, CompositionConfig
from agent3_montage.renderers.hyperframes import HyperframesRenderer
from agent3_montage.renderers.remotion import RemotionRenderer
from agent3_montage.renderers.ffmpeg_only import FFmpegOnlyRenderer

logger = logging.getLogger(__name__)


class RendererFactory:
    """Factory qui détecte et instancie le meilleur renderer disponible."""

    @staticmethod
    async def create() -> AbstractRenderer:
        """Détecte et retourne le renderer disponible le plus performant."""
        # 1. Hyperframes (canonique)
        hf = HyperframesRenderer()
        if await hf.is_available():
            logger.info("🎬 Using Hyperframes renderer (canonical)")
            return hf

        # 2. Remotion (fallback OSS)
        rm = RemotionRenderer()
        if await rm.is_available():
            logger.info("🎬 Using Remotion renderer (fallback OSS)")
            return rm

        # 3. FFmpeg-only (fallback ultime)
        logger.warning("⚠️  No advanced renderer available. Using FFmpeg-only mode.")
        logger.warning(
            "Install Hyperframes (https://agen.com/hyperframes) or "
            "Remotion (npm i @remotion/renderer) for motion design compositions."
        )
        return FFmpegOnlyRenderer()

    @staticmethod
    async def create_preferred(preferred: str) -> AbstractRenderer:
        """Instancie un renderer spécifique par nom."""
        renderers = {
            "hyperframes": HyperframesRenderer(),
            "remotion": RemotionRenderer(),
            "ffmpeg": FFmpegOnlyRenderer(),
        }
        renderer = renderers.get(preferred.lower())
        if renderer is None:
            raise ValueError(
                f"Unknown renderer '{preferred}'. "
                f"Choices: {list(renderers.keys())}"
            )
        if not await renderer.is_available():
            raise RuntimeError(
                f"Renderer '{preferred}' is not available on this system."
            )
        return renderer
