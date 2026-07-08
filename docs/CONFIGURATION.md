# Configuration — Video Automation Pipeline

## Structure de la Configuration Globale

Fichier : `config/config.yaml`

```yaml
# ═══════════════════════════════════════════════════════════════
# Configuration Globale — Video Automation Pipeline
# ═══════════════════════════════════════════════════════════════

pipeline:
  name: "Video Automation Pipeline"
  version: "1.0.0"
  
  # Mode d'exécution
  mode: "sequential"        # "sequential" | "parallel" (réservé futur)
  
  # Répertoires de données (montés en volumes Docker)
  data_dirs:
    raw: "/data/raw"
    transcriptions: "/data/transcriptions"
    cutlists: "/data/cutlists"
    renders: "/data/renders"
    audio: "/data/audio"
    qa: "/data/qa"
    final: "/data/final"
    logs: "/data/logs"
  
  # Limites globales
  max_iterations: 3         # Boucle qualité max
  timeout_per_agent: 3600   # Timeout par agent (secondes)
  
  # Profil de montage actif
  profile: "natural"        # "aggressive" | "natural"

---

## Profils de Montage

### Profil "aggressive"

```yaml
# config/profiles/aggressive.yaml
profile:
  name: "aggressive"
  description: "Montage serré — coupe au maximum, rythme rapide"
  
  # Agent #1 — Transcription
  transcription:
    silence_threshold_db: -30       # Seuil bas → détecte plus de silences
    min_silence_duration: 0.3       # 300ms suffisent pour couper
    preferred_source: "whisperx"    # WhisperX pour la vitesse
    scribe_fallback: true           # Scribe V2 seulement si erreur
    
  # Agent #2 — Narrative
  narrative:
    compression_ratio_target: 0.55  # Vise 55% de la durée originale
    filler_word_threshold: 0.6     # Agressif sur les tics de langage
    pause_tolerance_ms: 400        # Coupe les pauses > 400ms
    repetition_sensitivity: 0.7    # Détecte les répétitions agressivement
    broll_frequency: "high"        # Beaucoup de B-rolls
    broll_min_duration: 1.5        # B-rolls courtes et fréquentes
    
    # Comportement LLM
    llm_temperature: 0.3           # Faible température pour plus de coupes
    llm_model: "claude-sonnet-4"   # Modèle le plus rapide
    
  # Agent #3 — Montage
  editing:
    pace: "fast"                   # Rythme rapide
    transition_default: "cut"      # Cut sec par défaut
    transition_duration: 0.3       # Transitions très courtes
    max_subtitle_length: 60        # 60 caractères max
    subtitle_animation: "slide"    # Animation simple
    layout_complexity: "simple"    # Layouts simples (1-2 éléments)
    
    # Hyperframes / Remotion
    render_quality: "medium"       # 720p, bitrate moyen
    resolution: "1920x1080"
    fps: 30
    
  # Agent #4 — Audio
  audio:
    music_genre: ["electronic", "lo-fi", "upbeat"]
    music_volume_db: -18           # Musique assez forte
    sfx_frequency: "high"          # Beaucoup de SFX
    ducking_amount_db: -8          # Ducking modéré
    compressor_threshold_db: -16
    
  # Agent #5 — Qualité
  quality:
    pass_threshold: 0.65           # Seuil de passage plus bas (65%)
    minimum_critical_score: 0.4    # Tolérant
    max_feedback_iterations: 2     # Moins d'itérations
```

### Profil "natural"

```yaml
# config/profiles/natural.yaml
profile:
  name: "natural"
  description: "Montage naturel — garde le flow, rythme posé"
  
  # Agent #1 — Transcription
  transcription:
    silence_threshold_db: -40       # Seuil haut → ne coupe que les vrais silences
    min_silence_duration: 0.8       # 800ms minimum
    preferred_source: "scribe_v2"   # Scribe V2 pour la précision
    scribe_fallback: false
    
  # Agent #2 — Narrative
  narrative:
    compression_ratio_target: 0.80  # Garde 80% de la durée originale
    filler_word_threshold: 0.85    # Tolérant sur les tics
    pause_tolerance_ms: 1200       # Tolère les pauses jusqu'à 1.2s
    repetition_sensitivity: 0.9    # Ne détecte que les répétitions flagrantes
    broll_frequency: "low"         # Peu de B-rolls
    broll_min_duration: 3.0        # B-rolls longues
    
    # Comportement LLM
    llm_temperature: 0.7           # Plus de créativité
    llm_model: "claude-opus-4"     # Modèle le plus performant
    
  # Agent #3 — Montage
  editing:
    pace: "calm"                   # Rythme posé
    transition_default: "fade"     # Fondus par défaut
    transition_duration: 0.8       # Transitions douces
    max_subtitle_length: 80        # 80 caractères max
    subtitle_animation: "typewriter" # Animation élégante
    layout_complexity: "medium"    # Layouts variés
    
    # Hyperframes / Remotion
    render_quality: "high"         # 1080p, bitrate élevé
    resolution: "1920x1080"
    fps: 30
    
  # Agent #4 — Audio
  audio:
    music_genre: ["ambient", "cinematic", "jazz"]
    music_volume_db: -24           # Musique discrète
    sfx_frequency: "low"           # SFX subtils
    ducking_amount_db: -12         # Ducking prononcé (voix claire)
    compressor_threshold_db: -20
    
  # Agent #5 — Qualité
  quality:
    pass_threshold: 0.80           # Seuil de passage élevé (80%)
    minimum_critical_score: 0.6    # Exigeant
    max_feedback_iterations: 3     # Jusqu'à 3 itérations
```

---

## Configuration par Agent

### Agent #1 : Transcription

```yaml
# agents/agent-1-transcription/config.yaml
agent:
  id: 1
  name: "Acquisition & Transcription"
  
  scribe_v2:
    api_url: "https://api.scribe.com/v2/transcribe"
    api_key_env: "SCRIBE_V2_API_KEY"
    model: "scribe-v2-large"
    language: "fr"
    max_retries: 3
    timeout: 600
    
  whisperx:
    model_size: "large-v3"       # WhisperX modèle
    device: "cpu"                 # CPU only
    compute_type: "int8"          # Quantification CPU
    batch_size: 16
    language: "fr"
    align: true                   # Alignment words
    diarize: false                # Diarization (optionnel)
    
  silence_detector:
    method: "rms+spectral"        # RMS + analyse spectrale
    threshold_db: -35             # Configurable par profil
    min_silence_duration: 0.5     # Configurable par profil
    window_size_ms: 50
    hop_size_ms: 25
    
  fusion:
    strategy: "scribe_preferred"  # Scribe en priorité, WhisperX en complément
    deduplicate: true
    merge_threshold_ms: 200       # Fusion segments proches
  
  output:
    format: "json"
    include_words: true           # Inclure mots individuels
    include_speakers: false
```

### Agent #2 : Narrative & Dérushage

```yaml
# agents/agent-2-narrative/config.yaml
agent:
  id: 2
  name: "Analyse Narrative & Dérushage"
  
  llm:
    provider: "openrouter"
    api_key_env: "OPENROUTER_API_KEY"
    model: "anthropic/claude-sonnet-4"  # Modèle par défaut
    temperature: 0.5                     # Surchargeable par profil
    max_tokens: 4096
    timeout: 120
    
  analysis:
    chunk_size: 512             # Mots par chunk pour l'analyse LLM
    overlap_chunks: 0.1          # 10% overlap entre chunks
    max_retries_on_failure: 2
    fallback_strategy: "heuristic"  # "heuristic" | "simple_rules" si LLM fail
    
  derush:
    filler_words_file: "data/filler_words_fr.txt"  # Liste mots parasites FR
    custom_filler_words: ["euh", "bah", "en fait", "du coup", "voilà", "donc", "quoi"]
    pause_types: ["awkward", "thinking", "breathing"]
    
  broll:
    min_suggestion_confidence: 0.6
    max_suggestions_per_segment: 2
    broll_sources: ["stock", "screen", "generated"]
    stock_search_engine: "pexels"  # "pexels" | "unsplash" | "pixabay"
    
  clean_script:
    preserve_style: true          # Garder le style de l'orateur
    punctuation_model: "auto"     # Ponctuation automatique
```

### Agent #3 : Montage & Animation

```yaml
# agents/agent-3-editing/config.yaml
agent:
  id: 3
  name: "Montage & Animation"
  
  hyperframes:
    api_url: "http://hyperframes-api:3000/render"
    api_key_env: "HYPERFRAMES_API_KEY"
    resolution: "1920x1080"
    fps: 30
    codec: "h264"
    bitrate: "8M"               # Surchargeable par profil
    quality_preset: "medium"
    max_duration: 600           # 10 minutes max
    
  transitions:
    default: "cut"
    available:
      - "cut"
      - "fade"                  # Fondu enchaîné
      - "dissolve"              # Dissolution
      - "slide"                 # Glissement
      - "zoom"                  # Zoom
      - "wipe"                  # Balayage
      - "cross_zoom"            # Zoom croisé
    
  layouts:
    default: "fullscreen"
    available:
      - "fullscreen"            # Plein écran
      - "split_horizontal"      # Divisé horizontal
      - "split_vertical"        # Divisé vertical
      - "pip"                   # Picture-in-picture
      - "overlay_text"          # Texte superposé
      - "grid"                  # Grille
    
  subtitles:
    enabled: true
    font: "Inter"
    font_size: 48
    color: "#FFFFFF"
    background_color: "#00000080"  # Noir semi-transparent
    position: "bottom_center"
    max_chars_per_line: 60
    animation: "fade_in_out"
    
  motion_design:
    templates_dir: "templates/"
    default_template: "modern_minimal"
    color_scheme: "auto"        # "auto" | thème spécifique
```

### Agent #4 : Design Audio

```yaml
# agents/agent-4-audio/config.yaml
agent:
  id: 4
  name: "Design Audio"
  
  epidemic_sound:
    mcp_url: "https://mcp.epidemicsound.com/api"
    api_key_env: "EPIDEMIC_SOUND_API_KEY"
    search_limit: 20
    preview_duration: 30         # Secondes de preview
    
  music_selection:
    strategy: "mood_matching"    # Matching par humeur/rythme
    prefer_instrumental: true
    min_duration: 30             # Morceau minimum 30s
    max_duration: 600            # Morceau maximum 10min
    loop_if_shorter: true
    fade_in_ms: 1000
    fade_out_ms: 3000
    
  sfx:
    library: "epidemic_sound"
    categories:
      - "transition_whoosh"
      - "impact"
      - "ambience"
      - "ui_click"
      - "notification"
    auto_place: true             # Placement automatique SFX
    
  mixing:
    voice_volume_db: -3
    music_volume_db: -20         # Surchargeable par profil
    sfx_volume_db: -10
    ducking:
      enabled: true
      threshold_db: -20
      attack_ms: 50
      release_ms: 500
      reduction_db: -10         # Surchargeable par profil
    compressor:
      enabled: true
      threshold_db: -18
      ratio: 4
      attack_ms: 5
      release_ms: 100
    limiter:
      enabled: true
      threshold_db: -1
      release_ms: 100
```

### Agent #5 : Boucle Qualité

```yaml
# agents/agent-5-qa/config.yaml
agent:
  id: 5
  name: "Boucle Qualité"
  
  gemini:
    api_key_env: "GEMINI_API_KEY"
    model: "gemini-2.0-flash"    # Flash pour la vitesse
    vision_model: "gemini-2.0-flash"  # Vision analysis
    max_retries: 3
    timeout: 120
    frame_sample_rate: 10        # Analyser 1 frame toutes les 10s
    
  scoring:
    weights:
      narrative_coherence: 0.30
      audio_quality: 0.20
      visual_quality: 0.20
      pacing: 0.15
      motion_design: 0.10
      subtitle_accuracy: 0.05
    pass_threshold: 0.70         # Surchargeable par profil
    min_critical_score: 0.50     # Score minimum par catégorie
    
  feedback:
    enabled: true
    max_iterations: 3
    target_models:
      editing: "claude-sonnet-4"
      audio: "claude-sonnet-4"
      narrative: "claude-sonnet-4"
    feedback_format: "structured"  # "structured" | "free_text"
    
  analysis:
    analyze_transcript_coherence: true
    analyze_audio_sync: true
    analyze_visual_framing: true
    analyze_subtitle_timing: true
```

### Agent #6 : Orchestrator

```yaml
# agents/agent-6-orchestrator/config.yaml
agent:
  id: 6
  name: "Orchestrator"
  
  api:
    host: "0.0.0.0"
    port: 8080
    workers: 1
  
  cli:
    default_profile: "natural"
    verbose: false
    log_level: "INFO"            # "DEBUG" | "INFO" | "WARNING" | "ERROR"
  
  pipeline:
    sequential: true             # Mode séquentiel vs parallèle
    stop_on_failure: false       # Continuer si un agent échoue
    cleanup_temp_files: true     # Nettoyer les fichiers temporaires
    
  human_review:
    enabled: true                # Vérification humaine obligatoire
    dashboard_port: 8501         # Port Streamlit
    auto_approve_threshold: 0.95 # Score > 95% = approbation automatique possible
    review_timeout: 86400        # 24h max pour reviewer
    
  logging:
    level: "INFO"
    format: "json"               # "json" | "text"
    output_dir: "/data/logs"
    max_files: 30
    max_file_size_mb: 100
    include_timestamps: true
    
  notifications:
    enabled: false
    provider: "slack"            # "slack" | "email" | "webhook"
    webhook_url_env: "NOTIFICATION_WEBHOOK_URL"
    notify_on:
      - "pipeline_start"
      - "pipeline_complete"
      - "pipeline_failure"
      - "human_review_ready"
```

---

## Variables d'Environnement

```bash
# .env — Toutes les variables d'environnement du pipeline

# === APIs ===
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxx
SCRIBE_V2_API_KEY=scribe_xxxxxxxx
HYPERFRAMES_API_KEY=hf_xxxxxxxx
EPIDEMIC_SOUND_API_KEY=es_xxxxxxxx

# === Pipeline ===
PIPELINE_PROFILE=natural                 # "aggressive" | "natural"
PIPELINE_MODE=sequential
PIPELINE_MAX_ITERATIONS=3
PIPELINE_LOG_LEVEL=INFO

# === Docker ===
DOCKER_NETWORK=video-automation-network
DOCKER_DATA_DIR=./data

# === (Optionnel) Notifications ===
NOTIFICATION_WEBHOOK_URL=
SLACK_BOT_TOKEN=
SLACK_CHANNEL=#video-pipeline

# === (Optionnel) Monitoring ===
SENTRY_DSN=
LOGZIO_TOKEN=
```

---

## Validation de la Configuration

La configuration est validée au démarrage via Pydantic :

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

class PipelineConfig(BaseModel):
    name: str = "Video Automation Pipeline"
    version: str = "1.0.0"
    mode: Literal["sequential", "parallel"] = "sequential"
    profile: Literal["aggressive", "natural"] = "natural"
    max_iterations: int = Field(default=3, ge=1, le=10)
    timeout_per_agent: int = Field(default=3600, ge=60)
    
    @field_validator('max_iterations')
    @classmethod
    def validate_iterations(cls, v):
        if v > 5:
            import warnings
            warnings.warn("Plus de 5 itérations peut causer des timeouts")
        return v

def load_config(path: str = "config/config.yaml", profile: str | None = None) -> PipelineConfig:
    """Charge et fusionne la configuration globale + profil."""
    import yaml
    with open(path) as f:
        base = yaml.safe_load(f)
    
    if profile:
        profile_path = f"config/profiles/{profile}.yaml"
        try:
            with open(profile_path) as pf:
                profile_config = yaml.safe_load(pf)
            # Merge profond
            base = deep_merge(base, profile_config)
        except FileNotFoundError:
            pass
    
    return PipelineConfig(**base.get("pipeline", base))
```
