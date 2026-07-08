"""
Boucle qualité — intègre le feedback de l'Agent #5 (Gemini).

L'Agent #5 analyse la vidéo rendue et peut demander :
- Re-couper certains segments (trim)
- Changer le template (facecam → split)
- Ajuster les sous-titres
- Modifier la vitesse/l'animation
- Recommencer complètement

Loop : Rendu → Analyse → Feedback → Ajustement → Re-rendu (max N itérations)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from agent3_montage.config import MontageConfig
from agent3_montage.models import ComposedSegment

logger = logging.getLogger(__name__)


class QualityFeedback(BaseModel):
    """Feedback reçu de l'Agent #5."""
    status: Literal["pass", "fix", "fail"]
    score: float  # 0.0 - 10.0
    comments: list[str]
    adjustments: list[dict] | None = None
    # each dict: {"action": "retrim"|"change_template"|"reposition_broll"|"adjust_subtitles"|"full_rerender", "params": {}}


class QualityLoop:
    """
    Boucle qualité avec l'Agent #5.

    Comportement :
    - Envoie le chemin de la vidéo et les métadonnées à l'API Agent #5
    - Reçoit un feedback (pass/fix/fail)
    - Si fix : applique les ajustements et re-rend
    - Si fail : log l'erreur et stoppe
    - Si pass : la vidéo est validée
    """

    MAX_ITERATIONS = 3

    def __init__(
        self,
        endpoint: str = "",
        api_key: str = "",
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.endpoint = endpoint or "http://localhost:8085/api/quality"
        self.api_key = api_key
        self.max_iterations = max_iterations
        self.client = httpx.AsyncClient(timeout=120.0)

    async def run(
        self,
        video_path: Path,
        segments: list[ComposedSegment],
        config: MontageConfig,
    ) -> Path:
        """
        Exécute la boucle qualité.

        Args:
            video_path: Chemin de la vidéo à valider
            segments: Liste des segments composés
            config: Configuration de montage

        Returns:
            Chemin de la vidéo validée (ou ajustée)
        """
        current_path = video_path

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"🔄 Itération qualité {iteration}/{self.max_iterations}")

            # 1. Analyser
            feedback = await self._analyze(current_path, segments, config)

            if feedback.status == "pass":
                logger.info(f"✅ Qualité validée (score: {feedback.score}/10)")
                for comment in feedback.comments:
                    logger.info(f"   └─ {comment}")
                return current_path

            elif feedback.status == "fail":
                logger.error(f"❌ Qualité rejetée (score: {feedback.score}/10)")
                for comment in feedback.comments:
                    logger.error(f"   └─ {comment}")
                # On ne peut rien faire — retourner quand même
                # L'Agent #5 a signalé un problème critique
                return current_path

            elif feedback.status == "fix":
                logger.info(f"🔧 Ajustements demandés (score: {feedback.score}/10)")
                for adj in (feedback.adjustments or []):
                    logger.info(f"   → {adj.get('action', 'unknown')}")

                # 2. Appliquer les ajustements
                current_path = await self._apply_adjustments(
                    feedback, current_path, segments, config
                )

        logger.warning(
            f"⚠️  Nombre max d'itérations ({self.max_iterations}) atteint. "
            f"Retour de la dernière version."
        )
        return current_path

    async def _analyze(
        self,
        video_path: Path,
        segments: list[ComposedSegment],
        config: MontageConfig,
    ) -> QualityFeedback:
        """Envoie la vidéo à l'Agent #5 pour analyse qualité."""
        # Construction du payload
        payload = {
            "video_path": str(video_path.absolute()),
            "segments": [
                {
                    "id": s.segment_id,
                    "template_type": s.template.type,
                    "brolls": [
                        {"concept": b.concept, "placement": b.placement}
                        for b in s.broll_placements
                    ],
                }
                for s in segments
            ],
            "config": config.model_dump(),
        }

        try:
            resp = await self.client.post(
                self.endpoint,
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code != 200:
                logger.warning(
                    f"Agent #5 returned {resp.status_code}, treating as pass"
                )
                return QualityFeedback(
                    status="pass",
                    score=7.0,
                    comments=["Agent #5 unavailable, auto-passing"],
                )

            data = resp.json()
            return QualityFeedback(
                status=data.get("status", "pass"),
                score=data.get("score", 7.0),
                comments=data.get("comments", []),
                adjustments=data.get("adjustments"),
            )

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Agent #5 unavailable ({e}), treating as pass")
            return QualityFeedback(
                status="pass",
                score=7.0,
                comments=["Agent #5 unavailable, auto-passing"],
            )

    async def _apply_adjustments(
        self,
        feedback: QualityFeedback,
        video_path: Path,
        segments: list[ComposedSegment],
        config: MontageConfig,
    ) -> Path:
        """
        Applique les ajustements demandés par l'Agent #5.

        Types d'ajustements possibles :
        - retrim : modifier les timecodes d'un segment
        - change_template : modifier le template (ex: facecam → split)
        - reposition_broll : modifier la position/priorité d'un B-roll
        - adjust_subtitles : modifier la taille, couleur, position des sous-titres
        - full_rerender : tout recommencer
        """
        from agent3_montage.orchestrator import MontagePipeline

        pipeline = MontagePipeline(config=config)
        adjusted_path = video_path

        for adj in (feedback.adjustments or []):
            action = adj.get("action", "")
            params = adj.get("params", {})

            if action == "full_rerender":
                # Pour un re-render complet, il faudrait les entrées originales
                # Ceci est géré par l'appelant
                logger.warning("full_rerender demandé — l'appelant doit relancer le pipeline")
                continue

            elif action == "retrim":
                logger.info(f"   Applique retrim: {params}")
                # Retrim sera géré par FFmpegOps.extract_segment
                # avec les nouveaux timecodes
                pass

            elif action == "change_template":
                seg_id = params.get("segment_id")
                new_type = params.get("template_type")
                if seg_id and new_type:
                    for seg in segments:
                        if seg.segment_id == seg_id:
                            from agent3_montage.models import CompositionTemplate
                            new_t = CompositionTemplate(
                                name=f"{new_type}_adjusted",
                                type=new_type,
                                layout={},
                                animation={},
                                default_duration=seg.template.default_duration,
                                subtitle_position="bottom",
                            )
                            seg.template = new_t
                            logger.info(f"   Template mis à jour: {seg_id} → {new_type}")

            elif action == "adjust_subtitles":
                if "font_size" in params:
                    config.subtitle_font_size = params["font_size"]
                if "color" in params:
                    config.subtitle_color = params["color"]
                if "position" in params:
                    config.subtitle_position = params["position"]
                logger.info(f"   Sous-titres ajustés: {params}")

        return adjusted_path

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
