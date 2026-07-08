# 🎬 MontageAuto

**Pipeline de montage vidéo automatisé** — 6 agents interconnectés pour transformer une vidéo brute en produit monté, sans toucher à un timeline.

```
RAW → 🎙️ Transcription → 📝 Dérushage → ✂️ Montage → 🔊 Audio → ✅ Qualité → 🚀 Validation
```

---

## ⚡ Stack

| Composant | Technologie | Port |
|-----------|-------------|------|
| **Backend API** | FastAPI (Python 3.11) | `8001` |
| **Frontend UI** | Streamlit | `8502` |
| **Validation** | Pydantic / JSON Schema | — |
| **Rendu vidéo** | Hyperframes / Remotion / FFmpeg | — |
| **Transcription** | Whisper (via Scribe V2) | — |
| **Config** | YAML profils + merge hiérarchique | — |

---

## 🚀 Lancer le projet (depuis zéro)

### 1. Cloner

```bash
git clone git@github.com:Ilyas259/MontageAuto.git
cd MontageAuto
```

### 2. Installer les dépendances

```bash
# Créer un environnement virtuel (recommandé)
python3 -m venv .venv
source .venv/bin/activate

# Backend + Frontend
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 3. Lancer le backend

```bash
cd backend
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

Laisser tourner dans un terminal. Vérifier : `curl http://localhost:8001/health` → `{"status":"ok"}`

### 4. Lancer le frontend (autre terminal)

```bash
source .venv/bin/activate   # si pas déjà fait
cd frontend
streamlit run app.py --server.port 8502 --server.address 0.0.0.0
```

**Ouvrir** → http://localhost:8502

---

## 🧪 Workflow de test

1. **Onglet « ⚙️ Agents »** — explore tous les paramètres de chaque agent (transcription, dérushage, montage, audio, qualité, validation)
2. **Onglet « 🔐 Secrets »** — configure les clés API (DeepSeek pré-remplie, ajoute les autres au besoin)
3. **Onglet « ▶️ Pipeline »** — lance un pipeline avec les réglages choisis

---

## 🎛️ Paramètres disponibles

~**130 paramètres** répartis sur 6 agents :

| Agent | Paramètres | Exemples |
|-------|-----------|----------|
| **Transcription** | 21 | model_size, language, temperature, beam_size, vad_mode, hotwords, compute_type |
| **Dérushage** | 16 | profondeur_analyse, analyse_ia, system_prompt, preserve_questions, summary_style |
| **Montage** | 28 | resolution, fps, transitions, color_grade, ken_burns, aspect_ratio, sous_titres |
| **Audio** | 26 | music_genre, music_mood, ducking, voiceover, noise_reduction, LUFS, fade_duration |
| **Qualité** | 16 | seuils, check_audio_sync, frame_sample_rate, min_confidence, report_format |
| **Validation** | 14 | auto_approve, export_destination, notify_method, keep_intermediate |

---

## 📁 Structure du projet

```
MontageAuto/
├── backend/
│   ├── api/              # Routes FastAPI (agents, config, pipeline, secrets)
│   ├── config/           # Validateur Pydantic, engine de merge, loader YAML
│   │   └── profiles/     # Profils natural / aggressive / custom
│   └── orchestrator/     # Pipeline runner, state machine, log collector
├── frontend/
│   ├── components/       # Formulaire auto-généré, status pipeline
│   ├── pages/            # Agents, Pipeline, Secrets
│   └── services/         # Client API
├── shared/schemas/       # Contrats de données inter-agents
├── src/agent3_montage/   # Moteur de montage (renderers, templates, transitions)
├── docs/                 # Documentation technique complète
└── docker-compose.yml    # Déploiement conteneurisé
```

---

## 🐳 Docker (alternative)

```bash
docker compose up --build
```

---

## 📖 Documentation

| Doc | Description |
|-----|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Vue d'ensemble, data flow, stack technique |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Config globale, profils, merge hiérarchique |
| [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) | Contrats d'interface JSON entre agents |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Docker Compose, volumes, déploiement |
| [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md) | Rendu formulaire, palette, documentation UI |

---

## 🔐 Gestion des secrets

Les clés API sont gérées via l'interface **onglet Secrets** (pas de fichiers `.env` traînants). DeepSeek est pré-remplie automatiquement. Les autres clés (Scribe V2, ElevenLabs, Gemini, Hyperframes, Epidemic Sound) sont à saisir dans l'UI.

---

## 🖥️ Serveur actuel

Le projet tourne sur le serveur de développement :
- **Backend :** http://192.168.1.39:8001
- **Frontend :** http://192.168.1.39:8502
- **API Docs :** http://192.168.1.39:8001/docs
