# Architecture Frontend — Pipeline Montage Vidéo

## Principes fondateurs

1. **API-first** : toute interaction passe par l'API REST. Le frontend est un client sans état.
2. **Schema-driven UI** : chaque agent expose son schéma de config via JSON Schema. Le frontend contient un composant générique unique `render_schema_form()`.
3. **Découplage total** : frontend remplaçable sans toucher au backend (un seul fichier d'accès API).
4. **Extensibilité sans code frontend** : ajouter un agent = modèle Pydantic + 1 ligne registry.

## Stack

- **Backend API** : FastAPI + Uvicorn (port 8001)
- **Orchestrateur** : state machine Python asynchrone
- **Frontend** : Streamlit (port 8502) — remplaçable par React/Vue plus tard
- **Base config** : fichiers YAML + Pydantic validation
- **Communication** : REST + SSE (logs temps réel)

## Structure des dossiers

```
video-automation/
├── backend/
│   ├── api/              # Routes FastAPI
│   │   ├── main.py       # App FastAPI + montage routes
│   │   ├── routes/
│   │   │   ├── pipeline.py   # CRUD pipeline + start
│   │   │   ├── config.py     # Config CRUD + merge
│   │   │   ├── agents.py     # Registry agents + schemas
│   │   │   └── logs.py       # SSE streaming logs
│   │   └── sse_manager.py    # Gestionnaire connexions SSE
│   ├── config/
│   │   ├── engine.py         # Merge 4 couches
│   │   ├── schemas.py        # Pydantic config models
│   │   ├── loader.py         # Chargement YAML
│   │   ├── validator.py      # Validation Pydantic
│   │   └── profiles/         # Profils par défaut
│   │       ├── aggressive.yaml
│   │       └── natural.yaml
│   ├── orchestrator/
│   │   ├── state_machine.py  # États pipeline
│   │   ├── pipeline_runner.py# Lancement séquentiel agents
│   │   ├── agent_registry.py # Catalogue des agents disponibles
│   │   └── log_collector.py  # Capture stdout/stderr
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Point d'entrée Streamlit
│   ├── pages/
│   │   ├── pipeline.py       # Lancer/voir pipeline
│   │   ├── config.py         # Paramétrer agents
│   │   └── history.py        # Historique pipelines
│   ├── components/
│   │   ├── schema_form.py    # Render générique JSON Schema → champs Streamlit
│   │   └── pipeline_status.py# Affichage état + logs
│   └── services/
│       └── api.py            # Client HTTP vers backend
├── docker-compose.yml
└── shared/schemas/            # Schémas Pydantic existants
```

## API REST — Contrat frontend/backend

### Pipeline
| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/pipeline` | Créer un pipeline (retourne `id`) |
| `GET` | `/api/v1/pipeline/{id}` | Statut actuel |
| `POST` | `/api/v1/pipeline/{id}/start` | Démarrer l'exécution |
| `POST` | `/api/v1/pipeline/{id}/cancel` | Annuler |
| `GET` | `/api/v1/pipeline/{id}/result` | Résultat final |
| `GET` | `/api/v1/pipeline/{id}/logs/stream` | SSE temps réel |
| `GET` | `/api/v1/pipelines` | Lister tous les pipelines |

### Configuration
| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/v1/agents` | Lister les agents disponibles |
| `GET` | `/api/v1/agents/{id}/schema` | JSON Schema de la config |
| `GET` | `/api/v1/agents/{id}/config` | Config actuelle (mergée) |
| `PUT` | `/api/v1/agents/{id}/config` | Sauvegarder config utilisateur |
| `POST` | `/api/v1/config/resolve` | Forcer le merge et retourner la config résolue |
| `GET` | `/api/v1/config/profiles` | Lister profils disponibles |

### État pipeline (state machine)
```
idle → running → agent_N_in_progress → running → ... → completed
  ↓       ↓                                        ↓
  ↓   cancelling → cancelled                      failed
  ↓                                                ↓
  ↓                                            paused → running
```

## Merge config — 4 couches

```
DEFAULTS (<- backend/config/profiles/*.yaml)
    ↓  (héritage de base)
PROFIL (<- backend/config/profiles/aggressive.yaml ou natural.yaml)
    ↓  (écrase DEFAULTS)
USER   (<- stockage local, modifié via PUT /api/v1/agents/{id}/config)
    ↓  (écrase PROFIL)
RUN    (<- paramètres one-shot envoyés au POST /pipeline)
    ↓  (écrase USER — utilisés seulement pour cette exécution)
RÉSOLU (= merge final appliqué à l'agent)
```

Le frontend envoie uniquement les valeurs brutes au `PUT`. Le backend applique le merge via `POST /api/v1/config/resolve`.

## Composant générique schema_form

Un seul composant Streamlit capable de render n'importe quel JSON Schema :

```python
# frontend/components/schema_form.py
def render_schema_form(schema: dict, current_values: dict, prefix: str = "") -> dict:
    """
    Parcourt un JSON Schema et génère les widgets Streamlit appropriés :
    - string → st.text_input / st.select (si enum)
    - number → st.number_input
    - boolean → st.checkbox / st.toggle
    - array  → st.multiselect ou répétition
    - object → sous-formulaires récursifs
    - integer → st.number_input(step=1)
    Retourne un dict {field: value} des valeurs saisies.
    """
```

**Extension pour nouveaux types de champs** : 3 lignes dans ce composant.

## Pipeline Runner

```python
# backend/orchestrator/pipeline_runner.py
class PipelineRunner:
    """
    - Reçoit une config mergée
    - Itère sur les agents dans l'ordre
    - Pour chaque agent :
        1. Met à jour le state machine (agent_N_in_progress)
        2. Lance le sous-processus Docker/script
        3. Capture stdout/stderr → SSE
        4. Valide le contrat de sortie
        5. Passe au suivant
    - Gère les erreurs (timeout, exit code ≠ 0)
    - Envoie l'événement 'completed' ou 'failed'
    """
```

## Événements SSE

```json
// Event stream: /api/v1/pipeline/{id}/logs/stream
data: {"type": "status",     "pipeline_id": "...", "state": "agent_3_in_progress", "timestamp": "..."}
data: {"type": "log",        "pipeline_id": "...", "agent": "transcription", "level": "INFO", "message": "...", "timestamp": "..."}
data: {"type": "progress",   "pipeline_id": "...", "agent": "transcription", "percent": 45, "timestamp": "..."}
data: {"type": "result",     "pipeline_id": "...", "agent": "transcription", "output": {...}, "timestamp": "..."}
data: {"type": "completed",  "pipeline_id": "...", "result": {...}, "timestamp": "..."}
data: {"type": "error",      "pipeline_id": "...", "agent": "transcription", "error": "...", "timestamp": "..."}
```

## Extensibilité — ajouter un agent

1. Créer un module Python dans `backend/agents/` ou un Dockerfile
2. Déclarer dans `agent_registry.py` :
   ```python
   AgentEntry(
       id="agent_6_new",
       name="Nouvel Agent",
       config_schema=NewAgentConfig,  # Pydantic → JSON Schema
       image="video-automation-agent-6:latest",
       order=6,
   )
   ```
3. **Zéro changement frontend.** Le composant `schema_form` lit le JSON Schema automatiquement.

## Intégration Docker

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports: ["8001:8001"]
    volumes: ["./shared:/app/shared", "./backend/config/profiles:/app/config/profiles"]
  frontend:
    build: ./frontend
    ports: ["8502:8502"]
    environment: [API_URL=http://backend:8001]
    depends_on: [backend]
```

## Notes d'implémentation

- Backend : Python 3.11+, FastAPI, Pydantic v2, uvicorn
- Frontend : Streamlit 1.35+, httpx pour l'appel API
- Pas de DB pour le prototype — fichiers JSON dans `~/.video-automation/data/`
- Les logs sont stockés en FIFO (max 1000 lignes par pipeline en mémoire)
- Timeout par agent : 30 min par défaut, configurable par agent
