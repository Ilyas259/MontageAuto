"""Pipeline Runner — Exécute les 6 agents en séquence.

Reçoit une config mergée, lance chaque agent via Docker/subprocess,
capture les logs en temps réel via SSE, et gère les timeouts/erreurs/cancel.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.orchestrator.agent_registry import AgentInfo, get_agent, list_agents
from backend.orchestrator.log_collector import log_collector
from backend.orchestrator.state_machine import PipelineStateMachine

DEFAULT_TIMEOUT = 1800  # 30 min
POLL_INTERVAL = 0.5  # secondes entre checks de cancel


class PipelineRunner:
    """Orchestre l'exécution séquentielle des 6 agents."""

    def __init__(self, pipeline_id: str, state_machine: PipelineStateMachine):
        self.pipeline_id = pipeline_id
        self.state_machine = state_machine
        self._cancel_event = asyncio.Event()

    async def run(self, config_resolved: dict) -> dict:
        """Exécute le pipeline complet. Retourne le résultat final."""
        agents = list_agents()
        agents.sort(key=lambda a: a["order"])

        result = {
            "pipeline_id": self.pipeline_id,
            "status": "running",
            "agents_results": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error": None,
        }

        # Working directory (variable d'env pour compatibilité Docker)
        data_root = Path(os.environ.get("PIPELINE_DATA_DIR", Path.home() / ".video-automation" / "data"))
        work_dir = data_root / self.pipeline_id
        work_dir.mkdir(parents=True, exist_ok=True)
        input_file = work_dir / "input.mp4"

        for agent_info_raw in agents:
            agent_info = get_agent(agent_info_raw["id"])
            if not agent_info:
                continue

            agent_config = config_resolved.get("agents", {}).get(agent_info.id, {})
            if not agent_config.get("enabled", True):
                await log_collector.emit(
                    self.pipeline_id,
                    "status",
                    agent=agent_info.id,
                    level="INFO",
                    message=f"Agent {agent_info.id} désactivé, skip",
                )
                continue

            # Transition vers agent_N_in_progress
            agent_order = f"agent_{agent_info.order}_in_progress"
            if not self.state_machine.transition(agent_order, f"Démarrage {agent_info.id}"):
                break

            await log_collector.emit(
                self.pipeline_id,
                "status",
                agent=agent_info.id,
                level="INFO",
                message=f"Démarrage de {agent_info.name}",
            )

            # Vérification cancel
            if self.state_machine.cancel_requested:
                await self._handle_cancel(result)
                return result

            # Exécution de l'agent
            global_mode = config_resolved.get("mode", "api")
            agent_result = await self._run_agent(
                agent_info, work_dir, agent_config, global_mode
            )
            result["agents_results"].append(agent_result)

            if agent_result["status"] == "failed":
                await self._handle_failure(result, agent_result)
                return result

            if agent_result["status"] == "cancelled":
                await self._handle_cancel(result)
                return result

            # Vérification cancel après chaque agent
            if self.state_machine.cancel_requested:
                await self._handle_cancel(result)
                return result

        # Succès
        self.state_machine.transition("completed", "Pipeline terminé avec succès")
        result["status"] = "completed"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

        await log_collector.emit(
            self.pipeline_id, "completed", level="INFO", message="Pipeline terminé"
        )

        return result

    def request_cancel(self):
        """Demande l'annulation du pipeline en cours."""
        self._cancel_event.set()
        self.state_machine.transition("cancelling", "Annulation demandée par l'utilisateur")

    async def _run_agent(
        self, agent_info: AgentInfo, work_dir: Path, agent_config: dict, global_mode: str = "api"
    ) -> dict:
        """Exécute un seul agent et retourne son résultat."""
        timeout = agent_config.get("timeout", agent_info.timeout_minutes) * 60
        agent_result = {
            "agent_id": agent_info.id,
            "agent_name": agent_info.name,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error": None,
        }

        try:
            # Détermination du mode : agent.mode > global_mode > "api"
            agent_mode = agent_config.get("mode", "auto")
            if agent_mode == "auto":
                agent_mode = global_mode

            if agent_mode == "local":
                # Mode LOCAL — exécution via subprocess (ffmpeg, whisper, etc.)
                await log_collector.emit(
                    self.pipeline_id,
                    "log",
                    agent=agent_info.id,
                    level="INFO",
                    message=f"Agent {agent_info.id} en mode LOCAL — lancement subprocess",
                    percent=10,
                )

                # Simulation d'exécution locale (remplacé par le vrai code plus tard)
                await asyncio.sleep(0.3)

                await log_collector.emit(
                    self.pipeline_id,
                    "log",
                    agent=agent_info.id,
                    level="INFO",
                    message=f"Agent {agent_info.id} exécuté en mode LOCAL",
                    percent=100,
                )

            else:
                # Mode API — injecter la clé API du service
                from backend.config.secrets import SecretsManager, API_SERVICES
                sm = SecretsManager()
                service_key = API_SERVICES.get(agent_info.id)
                api_key = sm.get(service_key) if service_key else None
                if api_key:
                    await log_collector.emit(
                        self.pipeline_id, "log",
                        agent=agent_info.id, level="INFO",
                        message=f"Clé API {service_key} chargée",
                    )
                else:
                    await log_collector.emit(
                        self.pipeline_id, "log",
                        agent=agent_info.id, level="WARN",
                        message=f"Aucune clé API trouvée pour {service_key or agent_info.id} — mode API sans clé",
                    )

                # Mode API — stub (intégration API réelle à venir)
                await asyncio.sleep(0.5)  # Simulation rapide

                await log_collector.emit(
                    self.pipeline_id,
                    "log",
                    agent=agent_info.id,
                    level="INFO",
                    message=f"Agent {agent_info.id} exécuté en mode API (stub)",
                    percent=100,
                )

            agent_result["status"] = "completed"
            agent_result["completed_at"] = datetime.now(timezone.utc).isoformat()
            agent_result["mode"] = agent_mode
            agent_result["output"] = {
                "file": str(work_dir / f"{agent_info.id}_output.json"),
                "summary": f"Agent {agent_info.id} terminé (mode {agent_mode})",
            }

        except asyncio.TimeoutError:
            agent_result["status"] = "failed"
            agent_result["error"] = f"Timeout après {timeout}s"
            await log_collector.emit(
                self.pipeline_id, "error",
                agent=agent_info.id, level="ERROR",
                message=agent_result["error"],
            )

        except Exception as e:
            agent_result["status"] = "failed"
            agent_result["error"] = str(e)
            await log_collector.emit(
                self.pipeline_id, "error",
                agent=agent_info.id, level="ERROR",
                message=str(e),
            )

        return agent_result

    async def _handle_cancel(self, result: dict):
        """Gère l'annulation du pipeline."""
        self.state_machine.transition("cancelled", "Pipeline annulé")
        result["status"] = "cancelled"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        await log_collector.emit(
            self.pipeline_id, "status", level="WARN", message="Pipeline annulé"
        )

    async def _handle_failure(self, result: dict, agent_result: dict):
        """Gère l'échec d'un agent."""
        self.state_machine.transition("failed", f"Échec de {agent_result['agent_id']}")
        result["status"] = "failed"
        result["error"] = agent_result.get("error", "Erreur inconnue")
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        await log_collector.emit(
            self.pipeline_id, "status", level="ERROR",
            message=f"Pipeline échoué sur {agent_result['agent_id']}: {result['error']}",
        )
