# Architecture du Video Automation Pipeline

## 1. Vue d'Ensemble

Le **Video Automation Pipeline** est un système modulaire en 6 agents interconnectés. Chaque agent est un package Docker indépendant, communiquant via des contrats JSON strictement typés.

### Principe fondateur

> **"Better 10 videos at 80% than 1 at 100%"**
>
> Le système privilégie la production de masse avec une qualité suffisante (80%) plutôt que la perfection sur une seule vidéo. La boucle qualité (Agent #5) permet l'auto-amélioration continue.

---

## 2. Data Flow Global

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Agent #6 : Orchestrator                                 │
│                           (CLI / FastAPI / Streamlit Dashboard)                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
         │                            │                           │
         ▼                            ▼                           ▼
    ┌──────────┐               ┌───────────┐             ┌────────────┐
    │ Agent #1 │   ———[JSON]———▶│ Agent #2  │   ———[JSON]──▶│ Agent #3   │
    │ Transcr. │               │ Narrative │               │ Montage    │
    └──────────┘               │ & Dérush  │               │ & Animation│
         │                     └───────────┘               └──────┬─────┘
         ▼                                                       │
    ┌──────────┐                                                 │
    │ video.mp4│                                                 │
    │ (RAW in) │                                                 │
    └──────────┘                                                 │
                                                          ┌──────▼─────┐
                                                          │ Agent #4   │
                                                          │ Design     │
                                                          │ Audio      │
                                                          └──────┬─────┘
                                                                 │
                                                          ┌──────▼─────┐
                                                          │ Agent #5   │
                                                          │ Boucle     │
                                                          │ Qualité    │
                                                          └──────┬─────┘
                                                                 │
                                                          ┌──────▼─────┐
                                                          │ Agent #6   │
                                                          │ Human      │
                                                          │ Review     │
                                                          └────────────┘
                                                                 ▼
                                                          🎬 VIDEO FINALE
```

### Flux de données détaillé

```
ÉTAPE 1 : Acquisition & Transcription (Agent #1)
─────────────────────────────────────────────────
Entrée :  fichier vidéo (.mp4, .mov, .mkv)
Sortie : transcript.json  (JSON structuré)

Processus :
  1. Scribe V2 → Transcription principale (meilleure précision noms propres)
  2. WhisperX → Transcription secondaire avec erreurs + silences (timecodés)
  3. Détecteur de silence → Fichier des gaps temporels
  4. Fusion → Un transcript unifié avec :

     {
       "segments": [
         {
           "text": "La vidéo que tu vois à l'écran...",
           "start": 0.0,
           "end": 3.2,
           "confidence": 0.98,
           "speaker": null,
           "is_silence": false
         },
         { "start": 3.2, "end": 5.7, "is_silence": true, "type": "pause" }
       ],
       "metadata": { "duration": 124.5, "language": "fr" }
     }


ÉTAPE 2 : Analyse Narrative & Dérushage (Agent #2)
─────────────────────────────────────────────────────
Entrée :  transcript.json
Sortie : cutlist.json + script_nettoye.json + broll_suggestions.json

Processus (4 étapes) :
  1. Préparation du transcript (formatage, chunking)
  2. Logique de dérushage (analyse sémantique via LLM)
     → Repérage des erreurs, hésitations, répétitions
     → Définition des segments à garder/couper
  3. Suggestion de B-rolls (analyse de chaque segment conservé)
  4. Génération du script nettoyé (texte continu sans erreurs)


ÉTAPE 3 : Montage & Animation (Agent #3)
────────────────────────────────────────────
Entrée :  cutlist.json + broll_suggestions.json + vidéo brute
Sortie : montage_rendu.mp4 (vidéo montée)

Processus :
  1. Hyperframes (fork Remotion) → Génération HTML → Animation motion design
  2. Application des transitions (fondus, cut secs, glissades)
  3. Layouts et composition (PIP, split-screen, overlays)
  4. Sous-titres animés synchronisés


ÉTAPE 4 : Design Audio (Agent #4)
─────────────────────────────────────
Entrée :  montage_rendu.mp4 + metadata (humeur, rythme, couleurs)
Sortie : montage_audio.mp4 (avec bande-son)

Processus :
  1. Analyse du rythme de la vidéo montée
  2. Sélection musique via Epidemic Sound MCP (matching mood)
  3. Sound design : effets (transition, accentuation, ambiances)
  4. Mixage : ducking automatique (musique sous la voix)
  5. Export final du master audio


ÉTAPE 5 : Boucle Qualité (Agent #5)
──────────────────────────────────────
Entrée :  montage_audio.mp4
Sortie : rapport_qualite.json + (optionnel) feedback d'amélioration

Processus :
  1. Gemini analyse la vidéo (vision) → évaluation multi-critères
  2. Comparaison avec le brief original
  3. Si score < seuil → génération de feedback pour Claude/Codex
  4. Boucle d'auto-amélioration (max 3 itérations)
  5. Scores : rythme, cohérence narrative, qualité audio, motion design


ÉTAPE 6 : Vérification Humaine (Agent #6)
───────────────────────────────────────────
Entrée :  vidéo finale + tous les artefacts intermédiaires
Sortie : approbation_humaine.json

Processus :
  1. Orchestrator prépare le dossier de validation
  2. Streamlit dashboard : prévisualisation + métriques
  3. Vérification humaine obligatoire (les 3% résiduels)
  4. Signature + export production ou rejet/retour itération
```

---

## 3. Schéma Entrées/Sorties par Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Agent #1            │ Agent #2            │ Agent #3                        │
│ Acquisition         │ Narrative           │ Montage                         │
│ & Transcription     │ & Dérushage         │ & Animation                     │
├─────────────────────┼─────────────────────┼────────────────────────────────┤
│ IN: video.mp4      │ IN: transcript.json │ IN: cutlist.json                │
│                     │                     │     broll_suggestions.json      │
│ OUT: transcript.json│                     │     video(s) brute(s)          │
│      silence.json   │ OUT: cutlist.json  │                                 │
│                     │      script.json   │ OUT: montage_rendu.mp4          │
│                     │      broll.json    │                                 │
└─────────────────────┴─────────────────────┴────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────┐ ┌───────────────────────────┐
│ Agent #4            │ │ Agent #5            │ │ Agent #6                  │
│ Design Audio        │ │ Boucle Qualité      │ │ Orchestrator              │
├─────────────────────┼─────────────────────┼───────────────────────────┤
│ IN: montage.mp4    │ │ IN: montage.mp4    │ │ IN: Tous les artefacts   │
│     metadata.json   │ │     brief.json     │ │    précédents             │
│                     │ │                     │ │                           │
│ OUT: montage.mp4   │ │ OUT: qa_report.json│ │ OUT: video_finale.mp4    │
│      (avec audio)   │ │      feedback.json │ │      approval.json        │
│                     │ │      (optionnel)   │ │      logs complets        │
└─────────────────────┘ └─────────────────────┘ └───────────────────────────┘
```

---

## 4. Architecture Technique

### 4.1 Découpage en Packages

```
video-automation/
├── agents/
│   ├── agent-1-transcription/       # Package Docker séparable
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # Entrypoint CLI
│   │   │   ├── scribe_client.py    # Wrapper Scribe V2 API
│   │   │   ├── whisperx_client.py  # Wrapper WhisperX
│   │   │   ├── silence_detector.py # Algorithme de détection silence
│   │   │   ├── fusion.py           # Fusion des 3 sources
│   │   │   └── schemas.py          # Pydantic models
│   │   ├── config.yaml             # Config spécifique
│   │   └── requirements.txt
│   │
│   ├── agent-2-narrative/
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── narrative_analyzer/ # Module de dérushage
│   │   │   │   ├── __init__.py
│   │   │   │   ├── schemas.py     # ErrorDetection, KeptSegment, CutList...
│   │   │   │   ├── transcript_processor.py
│   │   │   │   ├── derush_logic.py # Logique sémantique
│   │   │   │   ├── broll_engine.py # Suggestion B-rolls
│   │   │   │   ├── script_cleaner.py
│   │   │   │   ├── llm_client.py   # OpenRouter / Claude
│   │   │   │   └── templates/      # Prompts Jinja2
│   │   │   │       ├── derush.jinja2
│   │   │   │       ├── broll.jinja2
│   │   │   │       └── clean.jinja2
│   │   │   └── schemas.py
│   │   ├── config.yaml
│   │   ├── prompts.yaml
│   │   └── requirements.txt
│   │
│   ├── agent-3-editing/
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── hyperframes_bridge.py # Appel API Hyperframes
│   │   │   ├── transition_engine.py
│   │   │   ├── layout_engine.py
│   │   │   ├── subtitle_renderer.py
│   │   │   └── schemas.py
│   │   ├── config.yaml
│   │   └── requirements.txt
│   │
│   ├── agent-4-audio/
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── epidemic_client.py    # MCP client Epidemic Sound
│   │   │   ├── sfx_engine.py        # Sound effects
│   │   │   ├── mix_engine.py        # Ducking, compression
│   │   │   └── schemas.py
│   │   ├── config.yaml
│   │   └── requirements.txt
│   │
│   ├── agent-5-qa/
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── gemini_analyzer.py   # Gemini Vision API
│   │   │   ├── feedback_generator.py # Feedback vers Claude/Codex
│   │   │   ├── scoring.py           # Système de score
│   │   │   └── schemas.py
│   │   ├── config.yaml
│   │   └── requirements.txt
│   │
│   └── agent-6-orchestrator/
│       ├── Dockerfile
│       ├── src/
│       │   ├── main.py              # CLI entrypoint
│       │   ├── api.py               # FastAPI server
│       │   ├── pipeline_manager.py  # Coordination des agents
│       │   ├── state_machine.py     # Workflow state machine
│       │   ├── human_review.py      # Dashboard Streamlit
│       │   ├── logger.py            # Logging structuré
│       │   └── schemas.py
│       ├── config.yaml
│       └── requirements.txt
│
├── shared/                          # Code partagé entre agents
│   ├── __init__.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── transcription.py        # Pydantic modèles communs
│   │   ├── narrative.py
│   │   ├── editing.py
│   │   ├── audio.py
│   │   └── qa.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── file_io.py              # helpers fichiers
│   │   ├── logging.py              # logging formaté
│   │   └── validation.py           # validateurs communs
│   └── config/
│       ├── __init__.py
│       ├── loader.py               # Chargeur config Pydantic
│       └── schema.py               # Schéma config global
│
├── config/
│   ├── config.yaml                 # Config globale
│   ├── profiles/
│   │   ├── aggressive.yaml         # Coupe plus, rythme rapide
│   │   └── natural.yaml            # Garde les hésitations, rythme lent
│   └── .env.example
│
├── data/                           # Volumes montés
│   ├── raw/                        # Vidéos brutes
│   ├── transcriptions/             # Sorties Agent #1
│   ├── cutlists/                   # Sorties Agent #2
│   ├── renders/                    # Sorties Agent #3
│   ├── audio/                      # Sorties Agent #4
│   ├── qa/                         # Rapports Agent #5
│   └── final/                      # Sortie finale Agent #6
│
├── docker-compose.yml
├── Dockerfile                     # Dockerfile racine (CLI)
├── pyproject.toml
├── Makefile
└── README.md
```

### 4.2 Communication entre Agents

Les agents communiquent **exclusivement par fichiers** via des volumes Docker montés sous `/data/`.

```
Agent #1 ──écrit──▶ /data/transcriptions/agent1_output.json
Agent #2 ──lit────▶ /data/transcriptions/agent1_output.json
Agent #2 ──écrit──▶ /data/cutlists/agent2_output.json
Agent #3 ──lit────▶ /data/cutlists/agent2_output.json
...
```

**Pattern :** *Publish-Subscribe sur système de fichiers.* Chaque agent lit son entrée depuis un dossier connu, écrit sa sortie dans un autre dossier connu. L'Orchestrator (Agent #6) gère le déclenchement.

### 4.3 Dépendances Entre Agents

```
Agent #1 (Transcription)    ──▶ Agent #2 (Narrative)
Agent #2 (Narrative)        ──▶ Agent #3 (Montage)
Agent #3 (Montage)          ──▶ Agent #4 (Audio)
Agent #4 (Audio)            ──▶ Agent #5 (Qualité)
Agent #5 (Qualité)          ──▶ Agent #6 (Orchestrator)
                                Agent #6 (Orchestr) ──▶ (fin ou boucle Agent #3)

Agent #1..5 ne se parlent pas directement.
Tout passe par l'Orchestrator.
```

### 4.4 Boucle d'Auto-Amélioration

```
Agent #5 ──(score < seuil)──▶ Feedback → Agent #2 (Nouveau cut suggéré)
                          ──▶ ou → Agent #3 (Nouveaux paramètres de rendu)
                          ──▶ ou → Agent #4 (Nouveau mix audio)
                                        
Limite : 3 itérations max par vidéo.
```

---

## 5. Stack Technique Détaillée

### 5.1 Langages & Frameworks

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| **Langage commun** | Python 3.11+ | Écosystème ML/LLM riche, maturité |
| **Validation** | Pydantic 2.7+ | Typage strict, sérialisation, validation |
| **Async** | asyncio + httpx | I/O non-bloquant, appels API LLM |
| **CLI** | click / typer | Interface utilisateur en ligne de commande |
| **API (Agent #6)** | FastAPI | Hautes performances, OpenAPI auto |
| **Dashboard** | Streamlit | Quick UI pour vérification humaine |
| **Container** | Docker | Isolation, reproductibilité |
| **Orchestration** | Docker Compose | Multi-container simple |

### 5.2 APIs Externes

| API | Usage | Agent concerné |
|-----|-------|----------------|
| **OpenRouter API** | Accès LLM (Claude, GPT-4, etc.) | #2, #5 |
| **Gemini API** | Vision (analyse vidéo) | #5 |
| **Scribe V2 API** | Transcription haute précision | #1 |
| **WhisperX** | Transcription secondaire (local CPU) | #1 |
| **Hyperframes API** | Rendu vidéo HTML → MP4 | #3 |
| **Epidemic Sound MCP** | Musiques & SFX libres de droits | #4 |

### 5.3 Fichiers & Formats

| Type | Format | Schema |
|------|--------|--------|
| Transcription | JSON | `TranscriptSchema` (Pydantic) |
| Cut list | JSON | `CutListSchema` (Pydantic) |
| Script nettoyé | JSON | `CleanScriptSchema` (Pydantic) |
| B-roll suggestions | JSON | `BRollSuggestionsSchema` (Pydantic) |
| Rapport qualité | JSON | `QaReportSchema` (Pydantic) |
| Feedback | JSON | `FeedbackSchema` (Pydantic) |
| Config | YAML | `ConfigSchema` (Pydantic) |
| Logs | JSON Lines | formaté |
| Vidéo finale | MP4 (H.264) | — |

### 5.4 Standards de Qualité

- **Typage strict** : 100% des données échangées sont typées via Pydantic
- **Validation** : Chaque entrée est validée au chargement
- **Logging structuré** : JSON Lines formaté pour ELK/Grafana
- **Tests** : pytest + pytest-asyncio (min. 80% coverage par agent)
- **Documentation** : README par agent + docstrings complètes

---

## 6. Déploiement

Voir [`DEPLOYMENT.md`](DEPLOYMENT.md) pour les détails Docker Compose.

---

## 7. Diagramme d'État du Pipeline

```
[IDLE] → NEW_JOB → TRANSCRIBING → ANALYZING → EDITING → 
         MIXING → QA_CHECK → [SCORE_OK] → HUMAN_REVIEW → 
         [APPROVED] → COMPLETED
                          │
                          └→ [SCORE_LOW] → ITERATING → EDITING
                                            (counter < 3)
                          └→ [REJECTED] → HUMAN_REVIEW → IDLE
```

Chaque transition est gérée par l'Orchestrator (Agent #6) via une machine d'états.
