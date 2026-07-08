"""Routes SSE pour le streaming de logs en temps réel."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_sse_manager
from backend.orchestrator.agent_registry import get_agent, list_agents

router = APIRouter()


@router.get("/pipeline/{pipeline_id}/logs/stream")
async def stream_pipeline_logs(pipeline_id: str, request: Request):
    """Endpoint SSE qui stream les logs d'un pipeline en temps réel."""
    sse_manager = get_sse_manager(request)
    queue = await sse_manager.subscribe(pipeline_id)

    return StreamingResponse(
        sse_manager.event_stream(pipeline_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
