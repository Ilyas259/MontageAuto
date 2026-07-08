"""/api/v1/agents routes (registry pur)."""

from fastapi import APIRouter, HTTPException

from backend.orchestrator.agent_registry import get_agent, list_agents
from backend.config.engine import ConfigEngine

router = APIRouter()
config_engine = ConfigEngine()


@router.get("/agents")
async def list_agents_endpoint():
    """Liste tous les agents disponibles."""
    return {"agents": list_agents()}


@router.get("/agents/{agent_id}")
async def get_agent_endpoint(agent_id: str):
    """Détail d'un agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} non trouvé")
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "docker_image": agent.docker_image,
        "input_file": agent.input_file,
        "output_file": agent.output_file,
        "order": agent.order,
        "timeout_minutes": agent.timeout_minutes,
    }
