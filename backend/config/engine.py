"""Moteur de configuration 4 couches.

Effectue le merge des configurations dans l'ordre :
    DEFAULTS → PROFIL (aggressive/natural) → USER → RUN

Chaque couche écrase les valeurs de la couche précédente.
Le résultat final est la config résolue appliquée aux agents.
"""

import json
from pathlib import Path
from typing import Any

from backend.config.loader import config_loader
from backend.config.validator import config_validator

USER_CONFIG_DIR = Path.home() / ".video-automation" / "config" / "user"


class ConfigEngine:
    """Moteur de merge des configurations 4 couches."""

    def __init__(self, profile: str = "natural"):
        self.current_profile = profile

    def resolve(self, agent_id: str, run_params: dict | None = None) -> dict:
        """Merge les 4 couches pour un agent et retourne la config résolue."""
        # Couche 1 : DEFAULTS
        defaults = self._get_defaults(agent_id)

        # Couche 2 : PROFIL
        profile_config = config_loader.load_profile(self.current_profile)
        profile_overrides = profile_config.get("agents", {}).get(agent_id, {})

        # Couche 3 : USER
        user_config = self._load_user(agent_id)

        # Couche 4 : RUN (paramètres one-shot)
        run_overrides = (run_params or {}).get(agent_id, {})

        # Merge successif
        resolved = {}
        resolved.update(defaults)
        resolved.update(profile_overrides)
        resolved.update(user_config)
        resolved.update(run_overrides)

        # Héritage du mode global du pipeline si "auto"
        pipeline_mode = profile_config.get("pipeline", {}).get("mode", "api")
        if resolved.get("mode", "api") == "auto":
            resolved["mode"] = pipeline_mode

        # Validation
        validation = config_validator.validate_agent_params(agent_id, resolved)
        if not validation.valid:
            resolved["_validation_errors"] = [e.model_dump() for e in validation.errors]

        return resolved

    def resolve_all(self, run_params: dict | None = None) -> dict:
        """Merge pour tous les agents."""
        from backend.orchestrator.agent_registry import list_agents
        result = {}
        for agent in list_agents():
            result[agent["id"]] = self.resolve(agent["id"], run_params)
        return result

    def get_schema(self, agent_id: str) -> dict:
        """Retourne le JSON Schema de configuration d'un agent."""
        return config_validator._get_agent_schema(agent_id)

    def save_user(self, agent_id: str, config: dict[str, Any]):
        """Sauvegarde la configuration utilisateur d'un agent."""
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = USER_CONFIG_DIR / f"{agent_id}.json"
        with open(path, "w") as f:
            json.dump(config, f, indent=2)

    def _load_user(self, agent_id: str) -> dict:
        """Charge la configuration utilisateur d'un agent."""
        path = USER_CONFIG_DIR / f"{agent_id}.json"
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    def list_profiles(self) -> list[str]:
        """Liste les profils disponibles."""
        return config_loader.list_profiles()

    @staticmethod
    def _get_defaults(agent_id: str) -> dict:
        """Retourne les valeurs par défaut d'un agent."""
        defaults = {
            "transcription": {
                "model_size": "large-v3",
                "language": "fr",
                "vad_sensitivity": 0.5,
                "min_silence_duration": 0.5,
                "mode": "auto",
            },
            "derushage": {
                "model": "deepseek",
                "temperature": 0.3,
                "keep_filler_words": False,
                "max_cut_duration": 60,
                "mode": "auto",
            },
            "montage": {
                "renderer": "hyperframes",
                "resolution": "1080p",
                "subtitles_enabled": True,
                "broll_enabled": True,
                "mode": "auto",
            },
            "audio": {
                "music_enabled": True,
                "music_volume": 0.15,
                "sfx_enabled": True,
                "ducking_level": 0.3,
                "mode": "auto",
            },
            "qualite": {
                "max_iterations": 3,
                "check_every_frame": False,
                "strictness": "medium",
                "mode": "auto",
            },
            "validation": {
                "require_approval": True,
                "notify_on_complete": True,
                "mode": "local",
            },
        }
        return defaults.get(agent_id, {})


config_engine = ConfigEngine()
