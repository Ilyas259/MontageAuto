"""
Système de sous-titres — mode karaoke, block, ou none.
Génération des événements et rendu via FFmpeg drawtext ou Hyperframes/Remotion.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent3_montage.models import (
    CutSegment,
    MontageConfig,
    SubtitleConfig,
    SubtitleEvent,
)

logger = logging.getLogger(__name__)


class SubtitleEngine:
    """
    Moteur de sous-titres.

    Supporte trois modes :
    - block : texte complet affiché en bloc
    - karaoke : mot par mot avec surlignage synchro
    - none : pas de sous-titres
    """

    def __init__(self, config: SubtitleConfig | None = None):
        self.config = config or SubtitleConfig()

    @classmethod
    def from_montage_config(cls, mc: MontageConfig) -> "SubtitleEngine":
        """Crée un SubtitleEngine à partir de la config de montage."""
        sc = SubtitleConfig(
            style=mc.subtitle_style,
            font=mc.subtitle_font,
            font_size=mc.subtitle_font_size,
            color=mc.subtitle_color,
            stroke_color=mc.subtitle_stroke_color,
        )
        return cls(sc)

    def generate_events(
        self,
        segments: list[CutSegment],
        words_timings: list[dict] | None = None,
    ) -> list[list[SubtitleEvent]]:
        """
        Génère les événements de sous-titres pour chaque segment.

        Args:
            segments: Liste des segments à sous-titrer
            words_timings: Timings mot-à-mot (optionnel, pour karaoke)

        Returns:
            Liste d'événements par segment
        """
        if self.config.style == "none":
            return [[] for _ in segments]

        events_by_segment = []
        for segment in segments:
            if self.config.style == "karaoke" and words_timings:
                events = self._generate_karaoke(segment, words_timings)
            else:
                events = self._generate_block(segment)
            events_by_segment.append(events)
        return events_by_segment

    def _generate_block(self, segment: CutSegment) -> list[SubtitleEvent]:
        """Mode bloc : tout le texte du segment en une fois."""
        if not segment.transcript.strip():
            return []

        duration = segment.end_time - segment.start_time
        if duration < 0.5:
            return []

        return [
            SubtitleEvent(
                text=segment.transcript.strip(),
                start_time=segment.start_time + 0.1,
                end_time=segment.end_time - 0.1,
                word_index=0,
            )
        ]

    def _generate_karaoke(
        self,
        segment: CutSegment,
        words_timings: list[dict],
    ) -> list[SubtitleEvent]:
        """Mode karaoke : un événement par mot avec timestamp."""
        seg_words = [
            w for w in words_timings
            if segment.start_time <= w.get("start", 0) < segment.end_time
        ]

        if not seg_words:
            return self._generate_block(segment)

        events = []
        for i, word in enumerate(seg_words):
            events.append(
                SubtitleEvent(
                    text=word.get("text", ""),
                    start_time=word.get("start", segment.start_time),
                    end_time=word.get("end", segment.end_time),
                    word_index=i,
                )
            )
        return events

    def render_block_ffmpeg(
        self,
        video_path: Path,
        events: list[SubtitleEvent],
        output_path: Path,
        resolution: tuple[int, int],
    ) -> Path:
        """
        Rendu des sous-titres en mode block via FFmpeg drawtext.

        Construit un filtre drawtext par événement avec activation temporelle.
        """
        if not events or self.config.style == "none":
            return video_path

        w, h = resolution
        filter_parts = []
        font = self.config.font

        for i, evt in enumerate(events):
            text = evt.text.replace("'", "'\\\\\\''").replace(":", "\\:")
            enable = f"between(t,{evt.start_time:.3f},{evt.end_time:.3f})"

            if self.config.position == "bottom":
                y = f"h-{self.config.margin_bottom}"
            elif self.config.position == "top":
                y = f"{self.config.margin_bottom}"
            else:
                y = "(h-text_h)/2"

            filter_parts.append(
                f"drawtext=text='{text}'"
                f":fontfile={font}"
                f":fontsize={self.config.font_size}"
                f":fontcolor={self.config.color}"
                f":borderw={self.config.stroke_width}"
                f":bordercolor={self.config.stroke_color}"
                f":x=(w-text_w)/2"
                f":y={y}"
                f":enable='{enable}'"
            )

        if not filter_parts:
            logger.warning("No subtitle filter parts generated, copying input.")
            return video_path

        vf = ",".join(filter_parts)

        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:a", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Subtitle burn failed: {result.stderr}")

        return output_path

    def render_karaoke_hyperframes(self, events: list[SubtitleEvent]) -> dict:
        """
        Génère les données de sous-titres karaoke pour le template Hyperframes.

        Returns:
            Dictionnaire JSON pour injection dans le template React
        """
        return {
            "type": "karaoke",
            "font": self.config.font,
            "font_size": self.config.font_size,
            "color": self.config.color,
            "highlight_color": self.config.karaoke_highlight_color,
            "advance_mode": self.config.karaoke_advance_mode,
            "stroke_color": self.config.stroke_color,
            "stroke_width": self.config.stroke_width,
            "position": self.config.position,
            "words": [
                {
                    "text": e.text,
                    "start": e.start_time,
                    "end": e.end_time,
                    "index": e.word_index,
                }
                for e in events
            ],
        }

    def export_srt(self, events: list[list[SubtitleEvent]], output_path: Path) -> Path:
        """Exporte les sous-titres au format SRT (sous-titres standard)."""
        lines = []
        idx = 1
        for segment_events in events:
            for evt in segment_events:
                start_srt = self._seconds_to_srt(evt.start_time)
                end_srt = self._seconds_to_srt(evt.end_time)
                lines.append(str(idx))
                lines.append(f"{start_srt} --> {end_srt}")
                lines.append(evt.text)
                lines.append("")
                idx += 1

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    @staticmethod
    def _seconds_to_srt(seconds: float) -> str:
        """Convertit des secondes en format SRT (HH:MM:SS,mmm)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
