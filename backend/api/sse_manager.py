"""Gestionnaire de connexions SSE (Server-Sent Events).

Maintient un ensemble de queues asyncio par pipeline_id.
Permet aux routes SSE de recevoir les événements en temps réel.
"""

import asyncio
import json
from typing import AsyncGenerator


class SseManager:
    """Manager thread-safe pour diffuser des événements SSE."""

    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, pipeline_id: str) -> asyncio.Queue:
        """Ajoute un abonné SSE pour un pipeline."""
        async with self._lock:
            if pipeline_id not in self._subscribers:
                self._subscribers[pipeline_id] = set()
            queue: asyncio.Queue = asyncio.Queue(maxsize=200)
            self._subscribers[pipeline_id].add(queue)
            return queue

    async def unsubscribe(self, pipeline_id: str, queue: asyncio.Queue):
        """Retire un abonné SSE."""
        async with self._lock:
            if pipeline_id in self._subscribers:
                self._subscribers[pipeline_id].discard(queue)
                if not self._subscribers[pipeline_id]:
                    del self._subscribers[pipeline_id]

    async def emit(self, pipeline_id: str, event_type: str, **data):
        """Émet un événement SSE à tous les abonnés d'un pipeline."""
        payload = {
            "type": event_type,
            "pipeline_id": pipeline_id,
            **data,
        }
        async with self._lock:
            queues = self._subscribers.get(pipeline_id, set()).copy()
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop le plus vieux message pour faire de la place
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except asyncio.QueueEmpty:
                    pass

    async def event_stream(
        self, pipeline_id: str, queue: asyncio.Queue
    ) -> AsyncGenerator[str, None]:
        """Génère le flux SSE pour un pipeline."""
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await self.unsubscribe(pipeline_id, queue)


sse_manager = SseManager()
