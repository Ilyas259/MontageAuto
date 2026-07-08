"""
Algorithme de placement des B-rolls dans la timeline.
Gère la priorité, les conflits, et la résolution des assets.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agent3_montage.config import MontageConfig
from agent3_montage.models import (
    BrollPlacement,
    ComposedSegment,
    CompositionTemplate,
    CutSegment,
)

logger = logging.getLogger(__name__)


class BrollPlacer:
    """
    Algorithme de placement des B-rolls dans la timeline.

    Stratégie :
    1. Filtrer et trier les suggestions par priorité décroissante
    2. Grouper par segment — chaque B-roll doit tomber dans son segment cible
    3. Résoudre les conflits temporels (deux fullscreen ne peuvent coexister)
    4. Assigner les assets disponibles (recherche dans les dossiers configurés)
    """

    def __init__(self, config: MontageConfig):
        self.config = config
        self.cache_dir = Path(config.cache_dir) / "broll_assets"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def place(
        self,
        segments: list[CutSegment],
        suggestions: list[BrollPlacement],
    ) -> list[ComposedSegment]:
        """
        Place les B-rolls dans les segments et retourne des ComposedSegment.

        Args:
            segments: Segments extraits de cut_list.json
            suggestions: Suggestions B-roll (brutes, avant filtrage)

        Returns:
            Liste de ComposedSegment avec B-rolls assignés
        """
        # 1. Filtrer et normaliser
        valid = self._filter_valid(suggestions)
        valid.sort(key=lambda b: b.priority, reverse=True)

        # 2. Grouper par segment
        segment_map = {s.id: s for s in segments}
        segment_brolls: dict[str, list[BrollPlacement]] = {s.id: [] for s in segments}

        for broll in valid:
            # Trouver le segment qui contient ce B-roll
            for seg in segments:
                if seg.start_time <= broll.start_time < seg.end_time:
                    segment_brolls[seg.id].append(broll)
                    break

        # 3. Résoudre les conflits par segment
        composed_segments = []
        for segment in segments:
            seg_brolls = self._resolve_overlaps(
                segment_brolls.get(segment.id, []), segment
            )
            composed = self._build_composed(segment, seg_brolls)
            composed_segments.append(composed)

        return composed_segments

    def _filter_valid(self, suggestions: list[BrollPlacement]) -> list[BrollPlacement]:
        """Filtre et normalise les suggestions B-roll."""
        valid = []
        for b in suggestions:
            duration = b.end_time - b.start_time
            if duration < 0.5:
                logger.warning(f"B-roll too short ({duration:.2f}s): {b.concept}")
                continue
            if duration < self.config.min_broll_duration:
                b.end_time = b.start_time + self.config.min_broll_duration
            if b.end_time - b.start_time > self.config.max_broll_duration:
                b.end_time = b.start_time + self.config.max_broll_duration
            valid.append(b)
        return valid

    def _resolve_overlaps(
        self,
        brolls: list[BrollPlacement],
        segment: CutSegment,
    ) -> list[BrollPlacement]:
        """
        Résout les conflits temporels entre B-rolls d'un même segment.

        Règles :
        - Deux fullscreen ne peuvent coexister → garder le plus prioritaire
        - overlay peut coexister avec fullscreen/split
        - split peut coexister avec facecam
        """
        if len(brolls) <= 1:
            return brolls

        overlays = [b for b in brolls if b.placement == "overlay"]
        fullscreens = [b for b in brolls if b.placement == "fullscreen"]
        splits = [b for b in brolls if b.placement == "split"]

        resolved_fs = self._deduplicate_overlapping(fullscreens)
        resolved_sp = self._deduplicate_overlapping(splits)

        # Tous les overlays sont gardés (ils se superposent)
        return resolved_fs + resolved_sp + overlays

    @staticmethod
    def _deduplicate_overlapping(
        brolls: list[BrollPlacement],
    ) -> list[BrollPlacement]:
        """Si des B-rolls du même type se chevauchent, garder le plus prioritaire."""
        if len(brolls) <= 1:
            return brolls

        brolls = sorted(brolls, key=lambda b: b.priority, reverse=True)
        result = [brolls[0]]

        for b in brolls[1:]:
            can_place = all(
                b.start_time >= placed.end_time or b.end_time <= placed.start_time
                for placed in result
            )
            if can_place:
                result.append(b)

        return result

    def _build_composed(
        self,
        segment: CutSegment,
        brolls: list[BrollPlacement],
    ) -> ComposedSegment:
        """Construit un ComposedSegment à partir d'un CutSegment et ses B-rolls."""
        # Déterminer le template en fonction du type et des B-rolls
        template_type = segment.type

        # Si un B-roll fullscreen est présent, forcer le type full_broll
        if any(b.placement == "fullscreen" for b in brolls):
            template_type = "full_broll"
        # Si un B-roll split est présent et que le segment est facecam, passer en split
        elif any(b.placement == "split" for b in brolls) and segment.type == "facecam":
            template_type = "split"

        template = CompositionTemplate(
            name=f"{template_type}_auto_{segment.id}",
            type=template_type,
            layout=self._get_layout_for_type(template_type),
            animation={"entry": {"type": "fade_in", "duration": 0.2}},
            default_duration=segment.end_time - segment.start_time,
            subtitle_position="bottom",
        )

        return ComposedSegment(
            segment_id=segment.id,
            template=template,
            source_clip=Path(),  # Sera défini après extraction FFmpeg
            broll_clips=[],      # Sera résolu par BrollAssetResolver
            broll_placements=brolls,
            subtitle_events=[],
        )

    @staticmethod
    def _get_layout_for_type(template_type: str) -> dict:
        layouts = {
            "facecam": {
                "speaker": {"x": 0, "y": 0, "w": 1, "h": 1, "fit": "cover"},
            },
            "split": {
                "speaker": {"x": 0, "y": 0, "w": 0.5, "h": 1, "fit": "cover"},
                "broll": {"x": 0.5, "y": 0, "w": 0.5, "h": 1, "fit": "cover"},
            },
            "full_broll": {
                "broll": {"x": 0, "y": 0, "w": 1, "h": 1, "fit": "cover", "ken_burns": True},
            },
            "transition": {},
        }
        return layouts.get(template_type, {})


class BrollAssetResolver:
    """
    Résout les chemins des assets B-roll.
    Cherche dans les dossiers configurés puis génère des placeholders si nécessaire.
    """

    def __init__(self, search_paths: list[Path], cache_dir: Path):
        self.search_paths = search_paths
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def resolve(self, broll: BrollPlacement) -> Path | None:
        """Trouve l'asset le plus pertinent pour une suggestion B-roll."""
        # 1. Chemin explicite
        if broll.asset_path:
            p = Path(broll.asset_path)
            if p.exists():
                return p

        # 2. Recherche par concept dans les dossiers
        for base_path in self.search_paths:
            candidates = self._search_by_concept(base_path, broll.concept)
            if candidates:
                return candidates[0]

        # 3. Placeholder
        logger.info(f"No asset found for '{broll.concept}', generating placeholder.")
        return self._generate_placeholder(broll)

    def _search_by_concept(self, base: Path, concept: str) -> list[Path]:
        """Recherche par mot-clé dans le dossier d'assets."""
        if not base.exists():
            return []
        results = []
        keywords = concept.lower().split()
        for f in base.iterdir():
            if f.is_file() and f.stem:
                stem_lower = f.stem.lower()
                if any(kw in stem_lower for kw in keywords):
                    results.append(f)
        return sorted(results)[:3]

    def _generate_placeholder(self, broll: BrollPlacement) -> Path:
        """
        Génère une vidéo placeholder avec texte du concept.

        Utilise FFmpeg pour créer un fond coloré avec drawtext.
        """
        safe_name = hashlib.md5(broll.concept.encode()).hexdigest()[:12]
        output = self.cache_dir / f"broll_placeholder_{safe_name}.mp4"

        if output.exists():
            return output

        # Version synchrone simplifiée — en prod, utiliser asyncio.create_subprocess_exec
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=#1a1a2e:s=1920x1080:d={self._duration_for_placeholder(broll)}",
            "-vf",
            f"drawtext=text='{broll.concept}':fontsize=48:"
            f"fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            str(output),
        ]
        subprocess.run(cmd, capture_output=True)
        return output

    @staticmethod
    def _duration_for_placeholder(broll: BrollPlacement) -> float:
        return max(2.0, broll.end_time - broll.start_time)
