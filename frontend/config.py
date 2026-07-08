"""Configuration du frontend Streamlit."""

import os

# URL de l'API backend (variable d'environnement ou défaut)
API_URL = os.environ.get("API_URL", "http://localhost:8001")

# Titre de l'application
APP_TITLE = "Pipeline Vidéo — Prototype"

# Profils disponibles
PROFILES = ["natural", "aggressive"]

# Ordre d'affichage des agents
AGENT_ORDER = [
    "transcription",
    "derushage",
    "montage",
    "audio",
    "qualite",
    "validation",
]

# Traductions et descriptions des agents
AGENT_LABELS = {
    "transcription": "🎙️ Transcription",
    "derushage": "✂️ Dérushage narratif",
    "montage": "🎬 Montage & animation",
    "audio": "🎵 Design audio",
    "qualite": "✅ Contrôle qualité",
    "validation": "👁️ Validation humaine",
}

AGENT_DESCRIPTIONS = {
    "transcription": "Transcrit la vidéo brute avec WhisperX + Scribe V2 (VAD, timestamps, locuteurs)",
    "derushage": "Analyse sémantique LLM — coupe, nettoie, structure le contenu narratif",
    "montage": "Hyperframes / Remotion / FFmpeg — montage final avec sous-titres et B-rolls",
    "audio": "Epidemic Sound + ducking automatique — musique, SFX, mixage voix",
    "qualite": "Gemini Vision — boucle de feedback qualité (max 3 itérations)",
    "validation": "Review humaine — dernier regard avant export final",
}

# Modes disponibles
MODES = ["api", "local", "auto"]
MODE_LABELS = {
    "api": "☁️ API (Cloud)",
    "local": "💻 Local (gratuit)",
    "auto": "🔄 Auto (profil)",
}
MODE_DESCRIPTIONS = {
    "api": "Utilise les API payantes (Scribe, ElevenLabs, Gemini, Hyperframes)",
    "local": "Exécution locale gratuite (Whisper, gTTS, Granite 2B, ffmpeg)",
    "auto": "Hérite du mode défini dans le profil sélectionné",
}

# Couleurs par état
STATE_COLORS = {
    "idle": "gray",
    "running": "blue",
    "agent_transcription_in_progress": "orange",
    "agent_derushage_in_progress": "orange",
    "agent_montage_in_progress": "orange",
    "agent_audio_in_progress": "orange",
    "agent_qualite_in_progress": "orange",
    "agent_validation_in_progress": "orange",
    "cancelling": "yellow",
    "cancelled": "gray",
    "completed": "green",
    "failed": "red",
}
