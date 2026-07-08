"""Chargeur de configuration — lit les fichiers YAML/JSON."""

import json
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Charge les fichiers de configuration avec fallback silencieux."""

    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            config_dir = str(Path(__file__).parent / "profiles")
        self.config_dir = Path(config_dir)

    def load_yaml(self, path: Path) -> dict[str, Any]:
        """Charge un fichier YAML, retourne dict vide si inexistant."""
        if not path.exists():
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def load_json(self, path: Path) -> dict[str, Any]:
        """Charge un fichier JSON, retourne dict vide si inexistant."""
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f) or {}

    def load_profile(self, name: str) -> dict[str, Any]:
        """Charge un profil par nom (aggressive, natural, etc.)."""
        yaml_path = self.config_dir / f"{name}.yaml"
        json_path = self.config_dir / f"{name}.json"
        if yaml_path.exists():
            return self.load_yaml(yaml_path)
        if json_path.exists():
            return self.load_json(json_path)
        return {}

    def list_profiles(self) -> list[str]:
        """Liste les profils disponibles (sans extension)."""
        profiles = []
        for f in self.config_dir.glob("*.yaml"):
            profiles.append(f.stem)
        for f in self.config_dir.glob("*.json"):
            if f.stem not in profiles:
                profiles.append(f.stem)
        return sorted(profiles)


config_loader = ConfigLoader()
