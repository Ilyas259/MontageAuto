# Déploiement — Video Automation Pipeline

## 1. Docker Compose — Architecture Complète

**Fichier :** `docker-compose.yml`

```yaml
# docker-compose.yml
version: "3.9"

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "10"
    tag: "{{.Name}}"

x-env: &common-env
  PIPELINE_PROFILE: ${PIPELINE_PROFILE:-natural}
  PIPELINE_LOG_LEVEL: ${PIPELINE_LOG_LEVEL:-INFO}
  OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:?error}
  GEMINI_API_KEY: ${GEMINI_API_KEY:?error}
  SCRIBE_V2_API_KEY: ${SCRIBE_V2_API_KEY}
  HYPERFRAMES_API_KEY: ${HYPERFRAMES_API_KEY}
  EPIDEMIC_SOUND_API_KEY: ${EPIDEMIC_SOUND_API_KEY}
  NOTIFICATION_WEBHOOK_URL: ${NOTIFICATION_WEBHOOK_URL:-}
  TZ: "Europe/Paris"

x-volumes: &data-volumes
  - type: bind
    source: ./data/raw
    target: /data/raw
  - type: bind
    source: ./data/transcriptions
    target: /data/transcriptions
  - type: bind
    source: ./data/cutlists
    target: /data/cutlists
  - type: bind
    source: ./data/renders
    target: /data/renders
  - type: bind
    source: ./data/audio
    target: /data/audio
  - type: bind
    source: ./data/qa
    target: /data/qa
  - type: bind
    source: ./data/final
    target: /data/final
  - type: bind
    source: ./data/logs
    target: /data/logs

services:
  # ──────────────────────────────────────────────────────────────
  # Agent #1 — Acquisition & Transcription
  # ──────────────────────────────────────────────────────────────
  agent-1-transcription:
    build:
      context: ./agents/agent-1-transcription
      dockerfile: Dockerfile
    image: video-automation/agent-1-transcription:latest
    container_name: agent-1-transcription
    environment:
      <<: *common-env
    volumes: *data-volumes
    logging: *default-logging
    restart: "no"
    command: ["video-automation-transcribe", "--input", "/data/raw", "--output", "/data/transcriptions"]
    profiles:
      - all
      - transcription

  # ──────────────────────────────────────────────────────────────
  # Agent #2 — Analyse Narrative & Dérushage
  # ──────────────────────────────────────────────────────────────
  agent-2-narrative:
    build:
      context: ./agents/agent-2-narrative
      dockerfile: Dockerfile
    image: video-automation/agent-2-narrative:latest
    container_name: agent-2-narrative
    environment:
      <<: *common-env
    volumes: *data-volumes
    logging: *default-logging
    restart: "no"
    depends_on:
      - agent-1-transcription
    command: [
      "video-automation-narrative",
      "--input", "/data/transcriptions",
      "--output", "/data/cutlists",
      "--profile", "${PIPELINE_PROFILE:-natural}"
    ]
    profiles:
      - all
      - narrative

  # ──────────────────────────────────────────────────────────────
  # Agent #3 — Montage & Animation
  # ──────────────────────────────────────────────────────────────
  agent-3-editing:
    build:
      context: ./agents/agent-3-editing
      dockerfile: Dockerfile
    image: video-automation/agent-3-editing:latest
    container_name: agent-3-editing
    environment:
      <<: *common-env
    volumes:
      <<: *data-volumes
      - ./agents/agent-3-editing/templates:/app/templates:ro
    logging: *default-logging
    restart: "no"
    depends_on:
      - agent-2-narrative
    command: [
      "video-automation-edit",
      "--cutlist", "/data/cutlists",
      "--raw", "/data/raw",
      "--output", "/data/renders",
      "--profile", "${PIPELINE_PROFILE:-natural}"
    ]
    profiles:
      - all
      - editing

  # ──────────────────────────────────────────────────────────────
  # Agent #4 — Design Audio
  # ──────────────────────────────────────────────────────────────
  agent-4-audio:
    build:
      context: ./agents/agent-4-audio
      dockerfile: Dockerfile
    image: video-automation/agent-4-audio:latest
    container_name: agent-4-audio
    environment:
      <<: *common-env
    volumes: *data-volumes
    logging: *default-logging
    restart: "no"
    depends_on:
      - agent-3-editing
    command: [
      "video-automation-audio",
      "--input", "/data/renders",
      "--metadata", "/data/cutlists",
      "--output", "/data/audio",
      "--profile", "${PIPELINE_PROFILE:-natural}"
    ]
    profiles:
      - all
      - audio

  # ──────────────────────────────────────────────────────────────
  # Agent #5 — Boucle Qualité
  # ──────────────────────────────────────────────────────────────
  agent-5-qa:
    build:
      context: ./agents/agent-5-qa
      dockerfile: Dockerfile
    image: video-automation/agent-5-qa:latest
    container_name: agent-5-qa
    environment:
      <<: *common-env
    volumes: *data-volumes
    logging: *default-logging
    restart: "no"
    depends_on:
      - agent-4-audio
    command: [
      "video-automation-qa",
      "--video", "/data/audio",
      "--cutlist", "/data/cutlists",
      "--output", "/data/qa",
      "--max-iterations", "${PIPELINE_MAX_ITERATIONS:-3}"
    ]
    profiles:
      - all
      - qa

  # ──────────────────────────────────────────────────────────────
  # Agent #6 — Orchestrator (API + CLI)
  # ──────────────────────────────────────────────────────────────
  agent-6-orchestrator:
    build:
      context: ./agents/agent-6-orchestrator
      dockerfile: Dockerfile
    image: video-automation/agent-6-orchestrator:latest
    container_name: agent-6-orchestrator
    environment:
      <<: *common-env
    volumes: *data-volumes
    ports:
      - "8080:8080"           # FastAPI
      - "8501:8501"           # Streamlit Dashboard
    logging: *default-logging
    restart: "unless-stopped"
    depends_on:
      - agent-1-transcription
      - agent-2-narrative
      - agent-3-editing
      - agent-4-audio
      - agent-5-qa
    profiles:
      - all
      - orchestrator
      - dashboard

  # ──────────────────────────────────────────────────────────────
  # CLI Wrapper — Accès en ligne de commande
  # ──────────────────────────────────────────────────────────────
  cli:
    build:
      context: .
      dockerfile: Dockerfile
    image: video-automation/cli:latest
    container_name: video-automation-cli
    environment:
      <<: *common-env
    volumes: *data-volumes
    logging: *default-logging
    restart: "no"
    entrypoint: ["video-automation"]
    profiles:
      - cli

networks:
  default:
    name: video-automation-network
    driver: bridge
```

---

## 2. Volumes et Arborescence des Données

```
./data/
├── raw/                    # Vidéos brutes (input)
│   ├── video_001.mp4
│   └── video_002.mov
│
├── transcriptions/         # Sortie Agent #1
│   └── transcript_video_001.json
│
├── cutlists/               # Sortie Agent #2
│   ├── cutlist_video_001.json
│   ├── script_video_001.json
│   └── broll_video_001.json
│
├── renders/                # Sortie Agent #3
│   └── render_video_001.mp4
│
├── audio/                  # Sortie Agent #4
│   └── audio_video_001.mp4
│
├── qa/                     # Sortie Agent #5
│   ├── qa_video_001.json
│   └── feedback_video_001.json
│
├── final/                  # Sortie Agent #6
│   └── final_video_001.mp4
│
└── logs/                   # Logs structurés
    └── pipeline_2025-07-08.jsonl
```

### Montage des Volumes

Tous les agents montent les mêmes volumes de données. Cela permet :

1. **Communication asynchrone** par fichiers
2. **Ré-exécution partielle** (un agent peut être relancé seul)
3. **Inspection humaine** à chaque étape
4. **Persistance** entre redémarrages Docker

---

## 3. Dockerfiles par Agent

### Pattern commun : Dockerfile multi-stage

```dockerfile
# agents/agent-X-*/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Isolation Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY src/ ./src/
COPY config.yaml .

# Image finale légère
FROM python:3.11-slim
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
WORKDIR /app

ENTRYPOINT ["python", "-m", "src.main"]
```

### Exemple : Agent #2 (Narrative)

```dockerfile
# agents/agent-2-narrative/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.11-slim
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "src.main"]
```

### Exemple : Agent #6 (Orchestrator — service long)

```dockerfile
# agents/agent-6-orchestrator/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.11-slim
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# FastAPI + Streamlit
EXPOSE 8080 8501

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 4. Variables d'Environnement

### Obligatoires

| Variable | Description | Source |
|----------|-------------|--------|
| `OPENROUTER_API_KEY` | Clé API OpenRouter | `.env` |
| `GEMINI_API_KEY` | Clé API Google Gemini | `.env` |

### Optionnelles

| Variable | Défaut | Description |
|----------|--------|-------------|
| `SCRIBE_V2_API_KEY` | — | Clé API Scribe V2 |
| `HYPERFRAMES_API_KEY` | — | Clé API Hyperframes |
| `EPIDEMIC_SOUND_API_KEY` | — | Clé API Epidemic Sound |
| `PIPELINE_PROFILE` | `natural` | Profil de montage actif |
| `PIPELINE_MAX_ITERATIONS` | `3` | Nombre max d'itérations QA |
| `PIPELINE_LOG_LEVEL` | `INFO` | Niveau de log |
| `NOTIFICATION_WEBHOOK_URL` | — | Webhook notifications |
| `TZ` | `Europe/Paris` | Fuseau horaire |

### Exemple .env

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-abc123def456
GEMINI_API_KEY=AIzaSyABC123DEF456
SCRIBE_V2_API_KEY=scribe_abc123
HYPERFRAMES_API_KEY=hf_abc123
EPIDEMIC_SOUND_API_KEY=es_abc123
PIPELINE_PROFILE=natural
PIPELINE_LOG_LEVEL=INFO
TZ=Europe/Paris
```

---

## 5. Commandes d'Orchestration

### Pipeline complet

```bash
# Lancer tout le pipeline (mode interactif)
docker compose --profile all up

# Attendre la fin du pipeline
docker compose --profile all up --abort-on-container-exit

# Lancer en arrière-plan
docker compose --profile all up -d
docker compose logs -f
```

### Agent individuel

```bash
# Transcription uniquement
docker compose run --rm agent-1-transcription \
  --input /data/raw/mon-interview.mp4

# Dérushage seul (si transcript déjà fait)
docker compose run --rm agent-2-narrative \
  --input /data/transcriptions/transcript.json \
  --profile aggressive

# Montage seul
docker compose run --rm agent-3-editing \
  --cutlist /data/cutlists/cutlist.json \
  --raw /data/raw \
  --output /data/renders
```

### Mode CLI (sans Docker Compose)

```bash
# Via le conteneur CLI
docker compose --profile cli run --rm cli \
  run --input /data/raw/mon-interview.mp4

# Sous-commandes
docker compose --profile cli run --rm cli \
  agent transcribe --input video.mp4
docker compose --profile cli run --rm cli \
  agent narrative --input transcript.json
```

### Dashboard de vérification humaine

```bash
# Lancer le dashboard Streamlit
docker compose --profile dashboard up -d

# Accès : http://localhost:8501
```

### Nettoyage

```bash
# Arrêter tous les services
docker compose down

# Nettoyer les volumes de données (attention : supprime tout)
docker compose down -v

# Nettoyer les images
docker compose down --rmi all
```

---

## 6. Déploiement Production (Recommandations)

### Architecture de déploiement

```
┌──────────────────────────────────────────────────┐
│              Reverse Proxy (Nginx/Caddy)          │
│              https://pipeline.exemple.com         │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│               Docker Compose (single host)         │
│                                                    │
│   agent-1  agent-2  agent-3  agent-4  agent-5    │
│                                                    │
│         agent-6 (Orchestrator + API)               │
│                                                    │
│         volumes: ./data/* (persistent)             │
└──────────────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│              Stockage persistant (NAS/S3)         │
│              /data/final/*.mp4 → archivage        │
└──────────────────────────────────────────────────┘
```

### Checklist production

- [ ] **Sécurité** : Clés API en `.env`, jamais commitées
- [ ] **Monitoring** : Logs JSON Lines → ELK / Loki + Grafana
- [ ] **Backups** : `./data/` sauvegardé quotidiennement
- [ ] **Ressources** : Min 4GB RAM, 2 CPU cores
- [ ] **Timeouts** : Ajustés selon la taille des vidéos
- [ ] **Notifications** : Slack/Email configuré pour les échecs
- [ ] **Rotating logs** : Logrotate ou Docker json-file limits
- [ ] **Healthcheck** : Agent #6 expose `/health` sur le port 8080

### Monitoring (Prometheus + Grafana)

```yaml
# docker-compose.monitoring.yml (extension optionnelle)
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
```

---

## 7. Makefile (Commandes Raccourcies)

```makefile
# Makefile
.PHONY: build up down run cli dashboard clean logs

# Construire toutes les images
build:
	docker compose build

# Lancer le pipeline complet
up:
	docker compose --profile all up --abort-on-container-exit

# Lancer en arrière-plan
up-d:
	docker compose --profile all up -d

# Arrêter tout
down:
	docker compose down

# Lancer un pipeline complet depuis le début
run:
	docker compose --profile all up --abort-on-container-exit

# CLI interactive
cli:
	docker compose --profile cli run --rm cli $(CMD)

# Dashboard humain
dashboard:
	docker compose --profile dashboard up -d

# Voir les logs
logs:
	docker compose logs -f

# Nettoyer tout
clean:
	docker compose down -v
	docker compose down --rmi all
```

---

## 8. Dépannage

### Problème : Un conteneur échoue

```bash
# Voir les logs détaillés
docker compose logs agent-2-narrative

# Relancer UN agent avec des paramètres de debug
docker compose run --rm agent-2-narrative \
  --input /data/transcriptions/transcript.json \
  --debug
```

### Problème : Timeout API LLM

```yaml
# Dans la config de l'agent concerné
llm:
  timeout: 300  # Augmenter le timeout à 5 minutes
  max_retries: 5
```

### Problème : WhisperX trop lent sur CPU

```yaml
# Dans la config Agent #1
whisperx:
  model_size: "base"       # Modèle plus petit = plus rapide
  compute_type: "int8"     # Quantification
  batch_size: 32           # Batch plus grand
```

### Problème : Volume non monté

```bash
# Vérifier les permissions
ls -la ./data/
chmod 755 ./data/*

# Vérifier les bind mounts
docker inspect agent-2-narrative | jq '.[].Mounts'
```
