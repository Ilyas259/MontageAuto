"""Registre des agents disponibles dans le pipeline.

Déclaration centralisée de tous les agents. Ajouter un agent = 1 entrée ici.
Le frontend lit cette liste pour générer l'interface automatiquement.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentInfo:
    id: str
    name: str
    description: str
    docker_image: str
    input_file: str | None
    output_file: str | None
    order: int
    timeout_minutes: int = 30
    config_schema: dict | None = None


# Registre statique des 6 agents du pipeline
AGENTS: list[AgentInfo] = [
    AgentInfo(
        id="transcription",
        name="Transcription (Scribe V2 + WhisperX)",
        description="Transcription audio/vidéo avec VAD, timestamps mots, détection silence",
        docker_image="video-automation-agent-1:latest",
        input_file="video_brute.mp4",
        output_file="transcript.json",
        order=1,
        timeout_minutes=60,
    ),
    AgentInfo(
        id="derushage",
        name="Dérushage Narratif (LLM)",
        description="Analyse sémantique du transcript, génération cut_list et script nettoyé",
        docker_image="video-automation-agent-2:latest",
        input_file="transcript.json",
        output_file="cut_list.json",
        order=2,
        timeout_minutes=15,
    ),
    AgentInfo(
        id="montage",
        name="Montage Vidéo (Hyperframes)",
        description="Montage final avec Hyperframes/Remotion/FFmpeg, sous-titres, B-rolls",
        docker_image="video-automation-agent-3:latest",
        input_file="cut_list.json",
        output_file="montage_rendu.mp4",
        order=3,
        timeout_minutes=120,
    ),
    AgentInfo(
        id="audio",
        name="Design Audio (Epidemic Sound)",
        description="Sound design, musique, ducking, effets sonores synchronisés",
        docker_image="video-automation-agent-4:latest",
        input_file="montage_rendu.mp4",
        output_file="audio_metadata.json",
        order=4,
        timeout_minutes=30,
    ),
    AgentInfo(
        id="qualite",
        name="Boucle Qualité (Gemini)",
        description="Feedback visuel/audio Gemini, re-render si nécessaire (max 3 itérations)",
        docker_image="video-automation-agent-5:latest",
        input_file="audio_metadata.json",
        output_file="qa_report.json",
        order=5,
        timeout_minutes=45,
    ),
    AgentInfo(
        id="validation",
        name="Validation Humaine",
        description="Review finale par un humain avant export",
        docker_image="",
        input_file="qa_report.json",
        output_file="validation_result.json",
        order=6,
        timeout_minutes=0,
    ),
]


def get_agent(agent_id: str) -> AgentInfo | None:
    """Retourne un agent par son ID."""
    for a in AGENTS:
        if a.id == agent_id:
            return a
    return None


def list_agents() -> list[dict]:
    """Retourne la liste des agents (format dict pour API)."""
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "order": a.order,
            "timeout_minutes": a.timeout_minutes,
        }
        for a in AGENTS
    ]
