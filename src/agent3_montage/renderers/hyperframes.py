"""
Renderer Hyperframes (par Agen) — renderer canonique.
Hyperframes transforme du HTML/CSS/JS en vidéo via une API HTTP.

Nécessite : service Hyperframes tournant sur localhost:3000
Licence : payant (Agen)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from agent3_montage.config import MontageConfig
from agent3_montage.models import ComposedSegment
from agent3_montage.renderers.base import AbstractRenderer, CompositionConfig

logger = logging.getLogger(__name__)


class HyperframesError(Exception):
    """Erreur Hyperframes."""
    pass


class HyperframesRenderer(AbstractRenderer):
    """
    Renderer utilisant Hyperframes (par Agen).

    Hyperframes expose une API REST sur localhost:3000 :
    - POST /api/compose  → crée un job de rendu
    - GET  /api/status/:id → statut du job
    - GET  /api/download/:id → télécharge le résultat
    """

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def is_available(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/health", timeout=5.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
        except Exception:
            return False

    async def get_version(self) -> str:
        try:
            resp = await self.client.get(f"{self.base_url}/api/version", timeout=5.0)
            return resp.json().get("version", "unknown")
        except Exception:
            return "unknown"

    async def get_name(self) -> str:
        return "Hyperframes"

    async def render(self, composition: CompositionConfig) -> Path:
        """Envoie la composition à Hyperframes et télécharge le résultat."""
        payload = self._build_payload(composition)

        resp = await self.client.post(
            f"{self.base_url}/api/compose",
            json=payload,
        )
        if resp.status_code != 200:
            raise HyperframesError(
                f"Compose API returned {resp.status_code}: {resp.text}"
            )

        job_id = resp.json()["id"]
        logger.info(f"Hyperframes job created: {job_id}")

        # Poll jusqu'à complétion
        while True:
            status = await self.client.get(
                f"{self.base_url}/api/status/{job_id}"
            )
            data = status.json()
            if data.get("status") == "completed":
                break
            elif data.get("status") == "failed":
                raise HyperframesError(
                    data.get("error", "Unknown render error")
                )
            await asyncio.sleep(2)

        # Télécharger
        download = await self.client.get(
            f"{self.base_url}/api/download/{job_id}"
        )
        composition.output_path.write_bytes(download.content)

        logger.info(f"Hyperframes render complete: {composition.output_path}")
        return composition.output_path

    async def render_preview(self, composition: CompositionConfig) -> Path:
        """Preview : même chose mais avec résolution réduite."""
        composition.config.preview_scale = 0.5
        composition.mode = "preview"
        return await self.render(composition)

    def _build_payload(self, composition: CompositionConfig) -> dict:
        """Convertit nos modèles en payload JSON pour l'API Hyperframes."""
        return {
            "resolution": composition.config.output_resolution,
            "fps": composition.config.fps,
            "tracks": [
                self._segment_to_track(s, composition.config)
                for s in composition.segments
            ],
            "subtitles": composition.subtitles,
            "output": {
                "format": "mp4",
                "codec": composition.config.codec,
                "crf": composition.config.crf,
            },
        }

    @staticmethod
    def _segment_to_track(
        segment: ComposedSegment,
        config: MontageConfig,
    ) -> dict:
        """Convertit un ComposedSegment en piste Hyperframes."""
        return {
            "type": "video",
            "src": str(segment.source_clip),
            "layout": segment.template.layout,
            "animation": segment.template.animation,
            "duration": segment.template.default_duration,
            "brolls": [
                {
                    "src": str(clip),
                    "placement": b.placement,
                    "transition": config.b_roll_transition,
                }
                for clip, b in zip(
                    segment.broll_clips,
                    segment.broll_placements,
                )
            ],
        }
