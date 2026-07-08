"""Gestion des secrets API (stockés hors dépôt, dans ~/.video-automation/secrets.yaml)."""

import os
from pathlib import Path
from typing import Dict, Optional
import yaml


SECRETS_DIR = Path.home() / ".video-automation"
SECRETS_FILE = SECRETS_DIR / "secrets.yaml"

# Services qui peuvent avoir une clé API
API_SERVICES = {
    "transcription": "scribe_v2",
    "derushage": "deepseek",
    "montage": "hyperframes",
    "audio": "elevenlabs",
    "qualite": "gemini",
    "audio_music": "epidemic_sound",
}

SERVICE_LABELS = {
    "scribe_v2": "Scribe V2",
    "deepseek": "DeepSeek LLM",
    "hyperframes": "Hyperframes",
    "elevenlabs": "ElevenLabs",
    "gemini": "Gemini",
    "epidemic_sound": "Epidemic Sound",
}


class SecretsManager:
    """Lit et écrit les clés API dans ~/.video-automation/secrets.yaml."""

    def __init__(self, secrets_file: Path = SECRETS_FILE):
        self.secrets_file = secrets_file
        self._secrets: Dict[str, str] = {}
        self._ensure_file()
        self._load()

    def _ensure_file(self):
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.secrets_file.exists():
            self.secrets_file.write_text("# API secrets — hors dépôt git\n# Ajoute tes clés ici ou via l'interface\n")
        # Crée un .gitignore si pas déjà fait
        gitignore = SECRETS_DIR / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n")

    def _load(self):
        if self.secrets_file.exists():
            content = self.secrets_file.read_text()
            try:
                self._secrets = yaml.safe_load(content) or {}
            except yaml.YAMLError:
                self._secrets = {}

    def _save(self):
        content = yaml.dump(self._secrets, default_flow_style=False, allow_unicode=True)
        self.secrets_file.write_text(f"# API secrets — hors dépôt git\n# Ajoute tes clés ici ou via l'interface\n\n{content}")

    def get(self, service: str) -> Optional[str]:
        return self._secrets.get(service)

    def set(self, service: str, key: str):
        self._secrets[service] = key
        self._save()

    def delete(self, service: str):
        self._secrets.pop(service, None)
        self._save()

    def get_all(self) -> Dict[str, str]:
        return dict(self._secrets)

    def is_configured(self, service: str) -> bool:
        return bool(self._secrets.get(service))
