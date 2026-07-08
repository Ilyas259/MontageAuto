"""API FastAPI — Pipeline Montage Vidéo"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import pipeline, config, agents, logs, secrets
from backend.api.sse_manager import sse_manager

app = FastAPI(
    title="Video Automation Pipeline API",
    version="0.1.0",
    description="API de pilotage du pipeline de montage vidéo automatisé",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router state (injecté dans l'app state pour les dépendances)
app.state.sse_manager = sse_manager

app.include_router(pipeline.router, prefix="/api/v1", tags=["Pipeline"])
app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(logs.router, prefix="/api/v1", tags=["Logs"])
app.include_router(secrets.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
