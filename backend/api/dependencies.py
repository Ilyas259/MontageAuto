"""Dépendances FastAPI réutilisables."""

from fastapi import Request

from backend.api.sse_manager import SseManager


def get_sse_manager(request: Request) -> SseManager:
    """Retourne l'instance SseManager depuis l'état de l'app."""
    return request.app.state.sse_manager
