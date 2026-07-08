"""
Orchestrateur central du pipeline de montage.
Enchaîne les étapes : lecture cut_list → découpage → templates → B-roll → sous-titres → rendu.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from agent3_montage.broll_placer import BrollAssetResolver, BrollPlacer
from agent3_montage.config import MontageConfig
from agent3_montage.ffmpeg_ops import FFmpegOps
from agent3_montage.models import (
    BrollPlacement,
    ComposedSegment,
    CutSegment,
    SegmentTemplate,
)
from agent3_montage.renderers import RendererFactory
from agent3_montage.renderers.base import CompositionConfig
from agent3_montage.subtitles import SubtitleEngine
from agent3_montage.template_engine import TemplateEngine
from agent3_montage.quality_loop import QualityLoop

logger = logging.getLogger(__name__)


class MontagePipeline:
    """
    Orchestrateur principal du pipeline de montage.

    Responsabilités :
    1. Charger la cut_list.json de l'Agent #2
    2. Initialiser les registres (templates, config)
    3. Exécuter le pipeline complet ou étape par étape
    4. Intégrer la boucle qualité Agent #5
    """

    def __init__(
        self,
        config: MontageConfig | None = None,
        config_path: Path | None = None,
    ):
        if config:
            self.config = config
        elif config_path:
            self.config = MontageConfig.load(config_path)
        else:
            self.config = MontageConfig()

        # Initialiser les sous-systèmes
        self.template_engine = TemplateEngine()
        self.broll_placer = BrollPlacer(self.config)
        self.subtitle_engine = SubtitleEngine.from_montage_config(self.config)
        self.ffmpeg = FFmpegOps()

        self.quality_loop = QualityLoop(
            self.config.quality_loop_endpoint,
            self.config.quality_loop_api_key,
        )

        self.temp_dir = Path(self.config.cache_dir) / "montage_work"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────
    # Pipeline complet
    # ──────────────────────────────────────────

    async def run(
        self,
        cut_list_path: Path,
        source_video: Path,
        output_path: Path,
        script_cleaned: Path | None = None,
        words_timings: list[dict] | None = None,
        preview: bool = False,
        skip_quality: bool = False,
    ) -> Path:
        """
        Exécute le pipeline complet.

        Args:
            cut_list_path: Chemin vers cut_list.json (Agent #2)
            source_video: Chemin vers la vidéo source brute
            output_path: Chemin de sortie de la vidéo finale
            script_cleaned: Script nettoyé (Agent #2) optionnel
            words_timings: Timings mot-à-mot optionnels (pour karaoke)
            preview: Mode preview (basse résolution)
            skip_quality: Sauter la boucle qualité Agent #5

        Returns:
            Chemin de la vidéo finale
        """
        start_total = time.time()
        logger.info("=" * 60)
        logger.info("🎬 Début du pipeline de montage Agent #3")

        # 1. Charger la cut_list
        logger.info(f"📋 Chargement cut_list: {cut_list_path}")
        segments, brolls = self._load_cut_list(cut_list_path)
        logger.info(f"   → {len(segments)} segments, {len(brolls)} suggestions B-roll")

        # 2. Résoudre les templates pour chaque segment
        logger.info("🎨 Résolution des templates...")
        for segment in segments:
            self.template_engine.resolve(segment, self.config)

        # 3. Découpage source via FFmpeg
        logger.info("✂️  Découpage des segments source...")
        segment_clips = await self._extract_segments(segments, source_video)

        # 4. Placement des B-rolls
        logger.info("🖼️  Placement des B-rolls...")
        composed = self.broll_placer.place(segments, brolls)

        # 5. Résoudre les assets B-roll
        logger.info("🔍 Résolution des assets B-roll...")
        resolver = BrollAssetResolver(
            search_paths=[Path(p) for p in self.config.broll_asset_dirs],
            cache_dir=Path(self.config.cache_dir) / "broll_assets",
        )
        for c_seg in composed:
            clips = []
            for broll in c_seg.broll_placements:
                path = await resolver.resolve(broll)
                if path:
                    clips.append(path)
            c_seg.broll_clips = clips
            if c_seg.segment_id in segment_clips:
                c_seg.source_clip = segment_clips[c_seg.segment_id]

        # 6. Générer les sous-titres
        logger.info("📝 Génération des sous-titres...")
        subtitle_events = self.subtitle_engine.generate_events(
            segments, words_timings
        )
        for i, c_seg in enumerate(composed):
            if i < len(subtitle_events):
                c_seg.subtitle_events = subtitle_events[i]

        # 7. Sélectionner et lancer le renderer
        logger.info("🎬 Lancement du rendu...")
        renderer = await RendererFactory.create()

        # Exporter SRT pour compatibilité
        srt_path = output_path.with_suffix(".srt")
        self.subtitle_engine.export_srt(subtitle_events, srt_path)

        # Préparer les données de sous-titres pour le renderer
        subtitles_data = self.subtitle_engine.render_karaoke_hyperframes(
            [e for seg_ev in subtitle_events for e in seg_ev]
        )

        composition = CompositionConfig(
            template=composed[0].template if composed else None,
            segments=composed,
            subtitles=subtitles_data,
            config=self.config,
            output_path=output_path,
            mode="preview" if preview else "final",
        )

        result = await renderer.render(composition)

        # 8. Boucle qualité (Agent #5)
        if not skip_quality:
            logger.info("🔄 Lancement boucle qualité Agent #5...")
            result = await self.quality_loop.run(
                video_path=result,
                segments=composed,
                config=self.config,
            )

        elapsed = time.time() - start_total
        logger.info(f"✅ Pipeline terminé en {elapsed:.1f}s")
        logger.info(f"   → Sortie : {result}")
        logger.info("=" * 60)

        return result

    # ──────────────────────────────────────────
    # Étapes individuelles
    # ──────────────────────────────────────────

    async def step_extract(
        self,
        source: Path,
        segments: list[CutSegment],
    ) -> dict[str, Path]:
        """Étape 1 : Extraction des segments."""
        return await self._extract_segments(segments, source)

    def step_template(
        self,
        segments: list[CutSegment],
    ) -> list[CompositionConfig]:
        """Étape 2 : Attribution des templates."""
        for seg in segments:
            self.template_engine.resolve(seg, self.config)

        # Retourne un config par segment
        return [
            CompositionConfig(
                template=self.template_engine.resolve(seg, self.config),
                segments=[],  # sera rempli après
                subtitles={},
                config=self.config,
                output_path=Path(),
                mode="final",
            )
            for seg in segments
        ]

    # ──────────────────────────────────────────
    # Interne
    # ──────────────────────────────────────────

    def _load_cut_list(self, path: Path) -> tuple[list[CutSegment], list[BrollPlacement]]:
        """Charge et parse la cut_list.json de l'Agent #2."""
        data = json.loads(path.read_text())
        segments = [CutSegment(**s) for s in data.get("segments", [])]
        brolls = [BrollPlacement(**b) for b in data.get("broll_suggestions", [])]
        return segments, brolls

    async def _extract_segments(
        self,
        segments: list[CutSegment],
        source: Path,
    ) -> dict[str, Path]:
        """Extrait chaque segment de la source vidéo."""
        segment_dir = self.temp_dir / "segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        tasks = []
        for seg in segments:
            out = segment_dir / f"seg_{seg.id}.mp4"
            tasks.append(
                FFmpegOps.extract_segment_accurate(
                    source, seg.start_time, seg.end_time, out
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        clip_map = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Extraction failed for segment {segments[i].id}: {result}"
                )
                continue
            clip_map[segments[i].id] = result

        logger.info(f"   → {len(clip_map)} segments extraits sur {len(segments)}")
        return clip_map
