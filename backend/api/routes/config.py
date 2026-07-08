"""Routes de configuration des agents.

Expose les schémas JSON Schema et la config mergée des agents.
Permet au frontend schema-driven de render les formulaires dynamiquement.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config.engine import ConfigEngine
from backend.orchestrator.agent_registry import get_agent, list_agents

router = APIRouter()

# Instance unique du moteur de config
config_engine = ConfigEngine()


@router.get("/agents")
async def list_all_agents():
    """Liste tous les agents disponibles avec leur état actif/inactif."""
    return list_agents()


@router.get("/agents/{agent_id}/schema")
async def get_agent_schema(agent_id: str):
    """Retourne le JSON Schema de la configuration d'un agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} non trouvé")

    schema = config_engine.get_schema(agent_id)
    return {"agent_id": agent_id, "schema": schema}


@router.get("/agents/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """Retourne la configuration mergée actuelle d'un agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} non trouvé")

    resolved = config_engine.resolve(agent_id)
    return {"agent_id": agent_id, "config": resolved}


@router.put("/agents/{agent_id}/config")
async def save_agent_config(agent_id: str, config: dict[str, Any]):
    """Sauvegarde la configuration utilisateur d'un agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} non trouvé")

    config_engine.save_user(agent_id, config)
    return {"agent_id": agent_id, "status": "saved"}


@router.post("/config/resolve")
async def resolve_config(pipeline_config: dict | None = None):
    """Force le merge complet et retourne la config résolue pour tous les agents.

    Pipeline_config peut contenir des run_params qui écrasent tout.
    """
    agents = list_agents()
    resolved = {}
    for agent_info in agents:
        agent_id = agent_info["id"]
        run_params = (pipeline_config or {}).get("run_params", {}).get(agent_id)
        resolved[agent_id] = config_engine.resolve(agent_id, run_params=run_params)

    return {
        "agents": resolved,
        "profile": config_engine.current_profile,
    }


@router.get("/config/profiles")
async def list_profiles():
    """Liste les profils de configuration disponibles."""
    return {"profiles": config_engine.list_profiles()}
