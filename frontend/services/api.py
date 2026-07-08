"""Service API — couche d'accès au backend FastAPI.

Toute communication frontend→backend passe par ce module.
Remplaçable par un client GraphQL ou REST plus sophistiqué plus tard.
"""

import json
from typing import Any

import httpx

from frontend.config import API_URL


class ApiClient:
    """Client HTTP pour l'API du pipeline."""

    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def list_agents(self) -> list[dict]:
        """Liste tous les agents disponibles."""
        resp = httpx.get(self._url("/agents"), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("agents", data) if isinstance(data, dict) else data

    def get_agent(self, agent_id: str) -> dict | None:
        """Détail d'un agent."""
        resp = httpx.get(self._url(f"/agents/{agent_id}"), timeout=5)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_agent_schema(self, agent_id: str) -> dict:
        """JSON Schema de configuration d'un agent."""
        resp = httpx.get(self._url(f"/agents/{agent_id}/schema"), timeout=5)
        resp.raise_for_status()
        return resp.json().get("schema", {})

    def get_agent_config(self, agent_id: str) -> dict:
        """Configuration mergée actuelle d'un agent."""
        resp = httpx.get(self._url(f"/agents/{agent_id}/config"), timeout=5)
        resp.raise_for_status()
        return resp.json().get("config", {})

    def save_agent_config(self, agent_id: str, config: dict) -> bool:
        """Sauvegarde la config utilisateur d'un agent."""
        resp = httpx.put(self._url(f"/agents/{agent_id}/config"), json=config, timeout=5)
        return resp.status_code == 200

    def list_profiles(self) -> list[str]:
        """Liste les profils disponibles."""
        resp = httpx.get(self._url("/config/profiles"), timeout=5)
        resp.raise_for_status()
        return resp.json().get("profiles", [])

    def resolve_config(self, run_params: dict | None = None) -> dict:
        """Force le merge complet pour tous les agents."""
        body = {"run_params": run_params} if run_params else None
        resp = httpx.post(self._url("/config/resolve"), json=body, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def create_pipeline(self, config: dict | None = None) -> dict:
        """Crée un nouveau pipeline."""
        resp = httpx.post(self._url("/pipeline"), json=config or {}, timeout=5)
        resp.raise_for_status()
        return resp.json()

    def get_pipeline(self, pipeline_id: str) -> dict:
        """Statut d'un pipeline."""
        resp = httpx.get(self._url(f"/pipeline/{pipeline_id}"), timeout=5)
        resp.raise_for_status()
        return resp.json()

    def start_pipeline(self, pipeline_id: str, run_config: dict | None = None) -> dict:
        """Démarre l'exécution d'un pipeline."""
        resp = httpx.post(
            self._url(f"/pipeline/{pipeline_id}/start"),
            json=run_config or {},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def cancel_pipeline(self, pipeline_id: str) -> dict:
        """Annule un pipeline."""
        resp = httpx.post(self._url(f"/pipeline/{pipeline_id}/cancel"), timeout=5)
        resp.raise_for_status()
        return resp.json()

    def get_pipeline_result(self, pipeline_id: str) -> dict:
        """Résultat final d'un pipeline."""
        resp = httpx.get(self._url(f"/pipeline/{pipeline_id}/result"), timeout=5)
        resp.raise_for_status()
        return resp.json()

    def list_pipelines(self, limit: int = 20) -> list[dict]:
        """Liste les pipelines récents."""
        resp = httpx.get(self._url(f"/pipelines?limit={limit}"), timeout=5)
        resp.raise_for_status()
        return resp.json()

    def get_logs_stream_url(self, pipeline_id: str) -> str:
        """URL du SSE pour les logs en temps réel."""
        return self._url(f"/pipeline/{pipeline_id}/logs/stream")


    # ── Secrets API ──────────────────────────────────────────────

    def _get(self, path: str, **kwargs) -> httpx.Response:
        resp = httpx.get(self._url(path), timeout=5, **kwargs)
        resp.raise_for_status()
        return resp

    def _post(self, path: str, **kwargs) -> httpx.Response:
        resp = httpx.post(self._url(path), timeout=5, **kwargs)
        resp.raise_for_status()
        return resp

    def _delete(self, path: str, **kwargs) -> httpx.Response:
        resp = httpx.delete(self._url(path), timeout=5, **kwargs)
        resp.raise_for_status()
        return resp

    def get_secrets(self) -> dict:
        r = self._get("/secrets/")
        return r.json()

    def get_secret(self, service: str) -> dict:
        r = self._get(f"/secrets/{service}")
        return r.json()

    def set_secret(self, service: str, api_key: str) -> dict:
        r = self._post("/secrets/", json={"service": service, "api_key": api_key})
        return r.json()

    def delete_secret(self, service: str) -> dict:
        r = self._delete(f"/secrets/{service}")
        return r.json()


# Singleton
api_client = ApiClient()
