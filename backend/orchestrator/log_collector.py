"""Collecteur de logs pour le pipeline.

Capture les logs de chaque agent et les achemine vers le SSE.
Stocke en FIFO (max 1000 lignes par pipeline).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.api.sse_manager import sse_manager

MAX_LOG_LINES = 1000


def _get_log_path(pipeline_id: str) -> Path:
    """Retourne le chemin du fichier de log pour un pipeline."""
    data_dir = Path.home() / ".video-automation" / "data" / pipeline_id
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "logs.jsonl"


class LogCollector:
    """Collecte et diffuse les logs d'exécution du pipeline."""

    def __init__(self):
        self._buffers: dict[str, list[dict]] = {}

    async def emit(
        self,
        pipeline_id: str,
        event_type: str,
        *,
        agent: str | None = None,
        level: str = "INFO",
        message: str = "",
        percent: float | None = None,
        output: dict | None = None,
        error: str | None = None,
        **extra: Any,
    ):
        """Émet un événement de log vers SSE + stockage."""
        entry = {
            "type": event_type,
            "pipeline_id": pipeline_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if agent:
            entry["agent"] = agent
        if level:
            entry["level"] = level
        if message:
            entry["message"] = message
        if percent is not None:
            entry["percent"] = percent
        if output is not None:
            entry["output"] = output
        if error is not None:
            entry["error"] = error
        entry.update(extra)

        # Push SSE (ne pas dupliquer pipeline_id — déjà passé comme premier argument)
        sse_data = {k: v for k, v in entry.items() if k != "pipeline_id"}
        await sse_manager.emit(pipeline_id, event_type, **sse_data)

        # Stockage FIFO
        if pipeline_id not in self._buffers:
            self._buffers[pipeline_id] = []
        buf = self._buffers[pipeline_id]
        buf.append(entry)
        if len(buf) > MAX_LOG_LINES:
            buf.pop(0)

        # Persist to disk (append-only JSONL)
        log_path = _get_log_path(pipeline_id)
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # Silence les erreurs d'écriture

    def get_logs(self, pipeline_id: str, limit: int = 200) -> list[dict]:
        """Retourne les derniers logs pour un pipeline."""
        buf = self._buffers.get(pipeline_id, [])
        return buf[-limit:]

    def clear(self, pipeline_id: str):
        """Vide les logs d'un pipeline."""
        self._buffers.pop(pipeline_id, None)
        log_path = _get_log_path(pipeline_id)
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass


log_collector = LogCollector()
