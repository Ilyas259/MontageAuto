"""Routes de gestion des pipelines : CRUD, start, cancel, résultat."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.orchestrator.agent_registry import list_agents
from backend.orchestrator.log_collector import log_collector
from backend.orchestrator.pipeline_runner import PipelineRunner
from backend.orchestrator.state_machine import PipelineStateMachine

router = APIRouter()

# Stockage en mémoire des pipelines (pour le prototype)
_pipelines: dict[str, dict[str, Any]] = {}
_runners: dict[str, PipelineRunner] = {}
_state_machines: dict[str, PipelineStateMachine] = {}


def _ensure_data_dir(pipeline_id: str) -> Path:
    """Crée et retourne le répertoire de données d'un pipeline."""
    d = Path.home() / ".video-automation" / "data" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_pipeline_meta(pipeline_id: str):
    """Persiste les métadonnées du pipeline sur disque."""
    meta = _pipelines.get(pipeline_id, {})
    data_dir = _ensure_data_dir(pipeline_id)
    (data_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))


def _on_state_change(pipeline_id: str, old_state: str, new_state: str, reason: str = ""):
    """Callback appelé à chaque transition d'état."""
    if pipeline_id in _pipelines:
        _pipelines[pipeline_id]["state"] = new_state
        _pipelines[pipeline_id]["last_transition"] = datetime.now(timezone.utc).isoformat()
        _save_pipeline_meta(pipeline_id)


@router.post("/pipeline")
async def create_pipeline(config: dict | None = None):
    """Crée un nouveau pipeline. Retourne son ID."""
    pipeline_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    pipeline = {
        "id": pipeline_id,
        "state": "idle",
        "created_at": now,
        "last_transition": now,
        "config": config or {},
        "agents": list_agents(),
        "result": None,
    }
    _pipelines[pipeline_id] = pipeline

    # State machine + runner
    sm = PipelineStateMachine(pipeline_id, on_transition=_on_state_change)
    _state_machines[pipeline_id] = sm
    _runners[pipeline_id] = PipelineRunner(pipeline_id, sm)

    _save_pipeline_meta(pipeline_id)

    return {"pipeline_id": pipeline_id, "state": "idle"}


@router.get("/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Retourne le statut actuel d'un pipeline."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trouvé")
    return pipeline


@router.post("/pipeline/{pipeline_id}/start")
async def start_pipeline(pipeline_id: str, run_config: dict | None = None):
    """Démarre l'exécution du pipeline."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trouvé")

    sm = _state_machines.get(pipeline_id)
    if not sm:
        raise HTTPException(status_code=400, detail="Pipeline non initialisé")

    if not sm.can_transition_to("running"):
        raise HTTPException(status_code=400, detail=f"Transition impossible depuis l'état {sm.state}")

    sm.transition("running", "Démarrage demandé")

    # Config mergée (simplifié pour le prototype)
    resolved_config = {
        "agents": {a["id"]: {"enabled": True} for a in pipeline["agents"]},
        "profile": pipeline.get("config", {}).get("profile", "natural"),
    }
    if run_config:
        resolved_config["run_params"] = run_config

    pipeline["state"] = "running"
    _save_pipeline_meta(pipeline_id)

    # Lancement asynchrone du runner
    runner = _runners[pipeline_id]
    import asyncio
    asyncio.create_task(_run_pipeline_async(pipeline_id, runner, resolved_config))

    return {"pipeline_id": pipeline_id, "state": "running"}


@router.post("/pipeline/{pipeline_id}/cancel")
async def cancel_pipeline(pipeline_id: str):
    """Annule un pipeline en cours."""
    runner = _runners.get(pipeline_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Pipeline non trouvé")

    runner.request_cancel()
    return {"pipeline_id": pipeline_id, "state": "cancelling"}


@router.get("/pipeline/{pipeline_id}/result")
async def get_pipeline_result(pipeline_id: str):
    """Retourne le résultat final d'un pipeline terminé."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trouvé")

    if pipeline["state"] not in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Pipeline pas encore terminé")

    return {
        "pipeline_id": pipeline_id,
        "state": pipeline["state"],
        "result": pipeline.get("result"),
    }


@router.get("/pipelines")
async def list_pipelines(limit: int = 20):
    """Liste les pipelines récents."""
    items = list(_pipelines.values())
    items.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return items[:limit]


async def _run_pipeline_async(pipeline_id: str, runner: PipelineRunner, config: dict):
    """Wrapper asynchrone pour l'exécution du pipeline."""
    try:
        result = await runner.run(config)
        if pipeline_id in _pipelines:
            _pipelines[pipeline_id]["result"] = result
            _pipelines[pipeline_id]["state"] = result["status"]
            _save_pipeline_meta(pipeline_id)
    except Exception as e:
        if pipeline_id in _pipelines:
            _pipelines[pipeline_id]["state"] = "failed"
            _pipelines[pipeline_id]["result"] = {"status": "failed", "error": str(e)}
            _save_pipeline_meta(pipeline_id)
