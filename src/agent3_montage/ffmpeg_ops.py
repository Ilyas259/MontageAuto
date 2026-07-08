"""
Opérations FFmpeg bas niveau — découpage, concaténation, encodage, synchronisation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from agent3_montage.config import MontageConfig
from agent3_montage.models import CompositionTemplate, SyncReport

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """Erreur FFmpeg."""
    pass


class FFmpegOps:
    """Opérations FFmpeg — découpage, concat, encodage, probes."""

    # ──────────────────────────────────────────
    # Probes & diagnostics
    # ──────────────────────────────────────────

    @staticmethod
    async def probe(path: Path) -> dict:
        """Analyse un fichier vidéo avec ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"FFprobe failed: {stderr.decode()}")
        return json.loads(stdout)

    @staticmethod
    def detect_sync_offset(video_path: Path) -> float:
        """
        Détecte le décalage audio/vidéo.

        Retourne l'offset en ms (>0 = audio en avance).
        """
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0.0

        data = json.loads(result.stdout)
        audio_streams = [s for s in data.get("streams", [])
                         if s["codec_type"] == "audio"]
        video_streams = [s for s in data.get("streams", [])
                         if s["codec_type"] == "video"]

        if not audio_streams or not video_streams:
            return 0.0

        audio_start = float(audio_streams[0].get("start_pts", 0))
        video_start = float(video_streams[0].get("start_pts", 0))
        audio_tb = audio_streams[0].get("time_base", "1/1000")
        video_tb = video_streams[0].get("time_base", "1/1000")

        # Convert time_base string to float
        def tb_to_float(tb_str: str) -> float:
            parts = tb_str.split("/")
            return float(parts[0]) / float(parts[1]) if len(parts) == 2 else float(parts[0])

        audio_ts = audio_start * tb_to_float(audio_tb) * 1000
        video_ts = video_start * tb_to_float(video_tb) * 1000

        return audio_ts - video_ts

    # ──────────────────────────────────────────
    # Extraction de segments
    # ──────────────────────────────────────────

    @staticmethod
    async def extract_segment(
        source: Path,
        start: float,
        end: float,
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Extrait un segment sans ré-encodage (stream copy).
        Rapide mais peut être imprécis sur les keyframes.
        """
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(output),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Segment extraction failed: {stderr.decode()}")
        return output

    @staticmethod
    async def extract_segment_accurate(
        source: Path,
        start: float,
        end: float,
        output: Path,
    ) -> Path:
        """
        Extraction précise avec ré-encodage pour les coupes exactes.
        À utiliser quand la précision à la frame est critique.
        """
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-ss", str(start),
            "-t", str(duration),
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            "-async", "1",
            "-af", "aresample=async=1:first_pts=0",
            str(output),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Accurate segment extraction failed: {stderr.decode()}")

        # Vérifier la sync
        offset = FFmpegOps.detect_sync_offset(output)
        if abs(offset) > 50:
            logger.warning(f"Audio sync offset {offset:.1f}ms detected in {output.name}")

        return output

    @staticmethod
    def safe_extract_cmd(source: Path, start: float, duration: float, output: Path) -> list[str]:
        """
        Commande FFmpeg sécurisée contre la désynchronisation audio.
        Combine -copyts, -async, et aresample pour garantir la sync.
        """
        return [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-copyts",
            "-async", "1",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "aresample=async=1:first_pts=0",
            str(output),
        ]

    # ──────────────────────────────────────────
    # Concaténation
    # ──────────────────────────────────────────

    @staticmethod
    async def concat_simple(segments: list[Path], output: Path) -> Path:
        """Concaténation simple sans transitions (concat demuxer)."""
        list_file = output.parent / "concat_list.txt"
        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg.absolute()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Concat failed: {stderr.decode()}")

        return output

    @staticmethod
    async def concat_with_transitions(
        segments: list[Path],
        transitions: list[CompositionTemplate],
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """Concatène avec transitions via filter complex (xfade)."""
        # Vérifier si des transitions non-cut sont demandées
        has_transitions = any(
            t.name not in ("transition_cut",) for t in transitions
        )

        if not has_transitions:
            return await FFmpegOps.concat_simple(segments, output)

        # Construction du filtre xfade pour les transitions
        # Chaque transition est entre segment i et i+1
        filter_parts = []
        input_labels = []
        segment_durations = []

        for i, seg in enumerate(segments):
            # Durée du segment
            dur = await FFmpegOps._get_duration(seg)
            segment_durations.append(dur)

        offset = 0.0
        for i, trans in enumerate(transitions):
            if i >= len(segments) - 1:
                break

            trans_dur = trans.default_duration or config.transition_duration

            # Type de transition ffmpeg xfade
            xfade_type = {
                "transition_fade": "fade",
                "transition_slide": "slideleft",
                "transition_zoom": "zoomin",
            }.get(trans.name, "fade")

            filter_parts.append(
                f"[{i}:v][{i+1}:v]xfade="
                f"transition={xfade_type}:"
                f"duration={trans_dur}:"
                f"offset={offset + segment_durations[i] - trans_dur}"
                f"[v{i+1}]"
            )
            offset += segment_durations[i]

        if not filter_parts:
            return await FFmpegOps.concat_simple(segments, output)

        # Dernière sortie vidéo
        last_idx = len(segments) - 1
        vf = ";".join(filter_parts)
        vf += f";[v{last_idx}]null[vout]"

        # Build command
        cmd = ["ffmpeg", "-y"]
        for seg in segments:
            cmd.extend(["-i", str(seg)])

        cmd.extend(["-filter_complex", vf])

        # Audio : concat simple
        audio_parts = "".join(f"[{i}:a]" for i in range(len(segments)))
        cmd.extend(["-filter_complex", f"{audio_parts}concat=n={len(segments)}:v=0:a=1[aout]"])

        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        cmd.extend([
            "-c:v", config.codec,
            "-crf", str(config.crf),
            "-preset", config.preset,
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            str(output),
        ])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Concat with transitions failed: {stderr.decode()}")

        return output

    @staticmethod
    async def _get_duration(video_path: Path) -> float:
        """Récupère la durée d'une vidéo en secondes."""
        data = await FFmpegOps.probe(video_path)
        return float(data.get("format", {}).get("duration", 0))

    # ──────────────────────────────────────────
    # Encodage final
    # ──────────────────────────────────────────

    @staticmethod
    async def encode_final(
        input_path: Path,
        output_path: Path,
        config: MontageConfig,
    ) -> Path:
        """Encodage final de la vidéo montée."""
        codec_map = {
            "h264": "libx264",
            "h265": "libx265",
            "h264_nvenc": "h264_nvenc",
            "h265_nvenc": "hevc_nvenc",
        }
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", codec_map[config.codec],
            "-crf", str(config.crf),
            "-preset", config.preset,
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            "-movflags", "+faststart",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Final encode failed: {stderr.decode()}")
        return output_path

    @staticmethod
    async def encode_preview(
        input_path: Path,
        output_path: Path,
        config: MontageConfig,
    ) -> Path:
        """Version preview rapide — résolution réduite, preset ultrafast."""
        pw, ph = config.preview_resolution.split("x")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"scale={pw}:{ph}",
            "-r", str(config.preview_fps),
            "-c:v", "libx264",
            "-crf", "28",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Preview encode failed: {stderr.decode()}")
        return output_path

    @staticmethod
    async def extract_audio(
        video_path: Path,
        output_path: Path,
        sample_rate: int = 44100,
    ) -> Path:
        """Extrait la piste audio d'une vidéo."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-ar", str(sample_rate),
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Audio extraction failed: {stderr.decode()}")
        return output_path
