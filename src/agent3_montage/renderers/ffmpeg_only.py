"""
Renderer FFmpeg-only — fallback ultime quand Hyperframes et Remotion sont indisponibles.
Assemble les segments avec overlay simple via les filtres FFmpeg.
Pas de motion design, pas d'animations complexes — juste du montage linéaire.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent3_montage.config import MontageConfig
from agent3_montage.ffmpeg_ops import FFmpegOps
from agent3_montage.renderers.base import AbstractRenderer, CompositionConfig

logger = logging.getLogger(__name__)


class FFmpegOnlyRenderer(AbstractRenderer):
    """
    Renderer minimal utilisant uniquement FFmpeg.

    Limitations :
    - Pas de motion design (animations, keyframes)
    - Pas de templates complexes (facecam incrustée)
    - Overlay basique via le filtre overlay de FFmpeg
    - Sous-titres via drawtext uniquement
    """

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def get_version(self) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            first_line = stdout.decode().split("\n")[0]
            return first_line.split("version")[-1].strip().split(" ")[0]
        except Exception:
            return "unknown"

    async def get_name(self) -> str:
        return "FFmpeg-only"

    async def render(self, composition: CompositionConfig) -> Path:
        """
        Rendu FFmpeg-only.

        Pour chaque segment, applique l'overlay si nécessaire (facecam incrustée,
        split screen, overlay B-roll), puis concatène le tout.

        Workflow :
        1. Pour chaque segment composé, créer un clip avec overlay
        2. Concaténer tous les clips
        3. Ajouter les sous-titres (drawtext)
        4. Encoder en final
        """
        temp_dir = composition.output_path.parent / "_ffmpeg_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        rendered_clips = []

        for i, segment in enumerate(composition.segments):
            seg_type = segment.template.type
            output_seg = temp_dir / f"seg_{i:04d}_{segment.segment_id}.mp4"

            if seg_type == "facecam":
                await self._render_facecam(segment, output_seg, composition.config)
            elif seg_type == "split":
                await self._render_split(segment, output_seg, composition.config)
            elif seg_type == "full_broll":
                await self._render_full_broll(segment, output_seg, composition.config)
            else:
                # Cut : copie directe
                await FFmpegOps.extract_segment(
                    segment.source_clip, 0,
                    segment.template.default_duration,
                    output_seg,
                    composition.config,
                )

            rendered_clips.append(output_seg)

        # Concaténer
        if not rendered_clips:
            raise RuntimeError("No segments rendered")

        concat_output = temp_dir / "_concat.mp4"
        await FFmpegOps.concat_simple(rendered_clips, concat_output)

        # Encoder final
        await FFmpegOps.encode_final(
            concat_output,
            composition.output_path,
            composition.config,
        )

        logger.info(f"FFmpeg-only render complete: {composition.output_path}")
        return composition.output_path

    async def render_preview(self, composition: CompositionConfig) -> Path:
        composition.mode = "preview"
        return await self.render(composition)

    async def _render_facecam(
        self,
        segment,  # ComposedSegment
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Rendu facecam simple : vidéo source avec overlay gradient subtil.

        Pas d'incrustation PIP — FFmpeg-only ne gère que le flux direct.
        """
        return await FFmpegOps.extract_segment(
            segment.source_clip, 0,
            segment.template.default_duration,
            output, config,
        )

    async def _render_split(
        self,
        segment,
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Rendu split screen via le filtre overlay FFmpeg.

        Utilise le filtre 'overlay' pour positionner speaker + broll
        côte à côte.
        """
        if not segment.broll_clips:
            return await self._render_facecam(segment, output, config)

        # Redimensionner et side-by-side via hstack
        w, h = config.output_size
        half_w = w // 2

        speaker = segment.source_clip
        broll = segment.broll_clips[0]
        temp1 = output.parent / f"_{segment.segment_id}_speaker.mp4"
        temp2 = output.parent / f"_{segment.segment_id}_broll.mp4"

        # Redimensionner chaque flux à la moitié de l'écran
        cmd = [
            "ffmpeg", "-y",
            "-i", str(speaker),
            "-i", str(broll),
            "-filter_complex",
            f"[0:v]scale={half_w}:{h},setsar=1[v0];"
            f"[1:v]scale={half_w}:{h},setsar=1[v1];"
            f"[v0][v1]hstack=inputs=2[vout]",
            "-map", "[vout]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output),
        ]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return output

    async def _render_full_broll(
        self,
        segment,
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Rendu full B-roll : le B-roll prend tout l'écran.
        Si pas de B-roll, copie la source (voice-over).
        """
        if segment.broll_clips:
            broll = segment.broll_clips[0]
            return await FFmpegOps.extract_segment(
                broll, 0,
                segment.template.default_duration,
                output, config,
            )
        return await FFmpegOps.extract_segment(
            segment.source_clip, 0,
            segment.template.default_duration,
            output, config,
        )
