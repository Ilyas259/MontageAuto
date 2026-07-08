# 🎬 Video Automation Pipeline

> **Montez vos vidéos automatiquement — 97% du montage, 0% de sueur.**
>
> *"Better 10 videos at 80% than 1 at 100%."*

Un système de **montage vidéo automatisé** en 6 agents interconnectés, capable de transformer une vidéo brute en un produit monté avec motion design, audio synchronisé, et boucle qualité auto-améliorative.

---

## Vision

Ce pipeline automatise **97% du workflow de montage vidéo** :

```
🎥 RAW → 🎙️ Transcription → 📝 Dérushage → ✂️ Montage → 🔊 Audio → ✅ QA → 🚀 LIVRAISON
```

Les 3% restants sont un **doute résiduel** — une vérification humaine finale obligatoire avant diffusion.

---

## Architecture en un coup d'œil

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Orchestrator (Agent #6)                         │
│  Pipeline coordination · Config globale · Logs · Vérification humaine  │
└───┬───────┬───────┬───────┬───────┬───────┬───────┬────────────────────┘
    │       │       │       │       │       │       │
    ▼       ▼       ▼       ▼       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │
│  #1    │ │  #2    │ │  #3    │ │  #4    │ │  #5    │ │  #6    │
│ Acquisition│ Analyse │ Montage │ Design  │ Boucle  │ Human  │
│ & Trans.│ & Dérush│ & Anim. │ Audio   │ Qualité │ Review │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## Les 6 Agents

| # | Agent | Technologie | Rôle |
|---|-------|-------------|------|
| 1 | **Acquisition & Transcription** | Scribe V2, WhisperX, silence detector | Transcrire la vidéo brute avec timecodes précis |
| 2 | **Analyse Narrative & Dérushage** | LLM + analyse sémantique | Générer la cut list, proposer des B-rolls, nettoyer le script |
| 3 | **Montage & Animation** | Hyperframes / Remotion, motion design | Produire la vidéo montée avec transitions et layouts |
| 4 | **Design Audio** | Epidemic Sound MCP, SFX | Ajouter musique, sound design, mixage |
| 5 | **Boucle Qualité** | Gemini API, feedback Claude/Codex | Analyser le rendu et auto-améliorer |
| 6 | **Orchestrator** | FastAPI, CLI, Docker Compose | Coordonner, logger, vérification humaine |

---

## Stack Technique

| Catégorie | Technologie | Version |
|-----------|-------------|---------|
| **Langage** | Python | 3.11+ |
| **Validation** | Pydantic | 2.7+ |
| **Conteneurisation** | Docker | 24+ |
| **Orchestration** | Docker Compose | V2+ |
| **Transcription** | Scribe V2 + WhisperX | latest |
| **Rendu vidéo** | Hyperframes (Remotion fork) | latest |
| **Audio** | Epidemic Sound MCP | latest |
| **LLM** | OpenRouter API, Gemini API | — |
| **Web** | FastAPI (agents), Streamlit (dashboard) | latest |
| **Async** | asyncio + httpx | — |

> **Zéro GPU nécessaire.** Tous les agents tournent sur CPU sauf mention contraire explicite.

---

## Prérequis

- Python 3.11+
- Docker & Docker Compose V2
- Clés API : OpenRouter, Gemini, Epidemic Sound
- Ubuntu 22.04+ (recommandé)

---

## Installation rapide

```bash
# 1. Cloner le dépôt
git clone https://github.com/redd/video-automation.git
cd video-automation

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos clés API

# 3. Lancer l'ensemble du pipeline
docker compose up --build

# 4. Ou lancer un agent spécifique
docker compose run agent-2-narrative \
  --input /data/raw/ma-video.mp4 \
  --config /app/config/profiles/aggressive.yaml
```

---

## Utilisation CLI

```bash
# Pipeline complet
video-automation run --input video.mp4

# Avec profil de montage
video-automation run --input video.mp4 --profile natural

# Agant individuel
video-automation agent transcribe --input video.mp4
video-automation agent narrative --input transcript.json
video-automation agent edit --input cutlist.json
video-automation agent audio --input edit.json
video-automation agent qa --input render.mp4

# Dashboard de suivi
video-automation dashboard
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Vue d'ensemble, data flow, stack technique |
| [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) | Contrats d'interface JSON entre agents |
| [`CONFIGURATION.md`](CONFIGURATION.md) | Config globale, profils, paramètres |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Docker Compose, volumes, déploiement |

---

## Workflow type

1. **Filmage** → Vidéo brute (MP4, MOV)
2. **Agent #1** → Transcription JSON avec timecodes + silences
3. **Agent #2** → Cut list + B-roll suggestions + script nettoyé
4. **Agent #3** → Rendu vidéo monté (Hyperframes/Remotion)
5. **Agent #4** → Audio final (musique + SFX synchronisés)
6. **Agent #5** → Validation qualité → feedback → itération (max 3)
7. **Agent #6** → Présentation à l'humain → approbation finale

---

## Contribution

Voir [`CONTRIBUTING.md`](CONTRIBUTING.md) (à venir).

---

## Licence

Propriétaire — Usage interne (Redd).
