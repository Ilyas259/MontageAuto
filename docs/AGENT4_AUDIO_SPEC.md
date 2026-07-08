# Agent #4 — Design Audio

> **Module responsable du design sonore final** : nettoyage de la voix, sélection musicale via Epidemic Sound MCP, placement d'effets sonores, mixage multipiste avec ducking automatique, et vérification de synchronisation.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture du module](#2-architecture-du-module)
3. [Pipeline d'exécution](#3-pipeline-dexécution)
4. [Modèles de données (Pydantic)](#4-modèles-de-données-pydantic)
5. [Configuration externalisable](#5-configuration-externalisable)
6. [MCP Epidemic Sound](#6-mcp-epidemic-sound)
7. [Audio Mixing Pipeline](#7-audio-mixing-pipeline)
8. [Ducking intelligent](#8-ducking-intelligent)
9. [Sync guard](#9-sync-guard)
10. [Boucle Qualité (Agent #5)](#10-boucle-qualité-agent-5)
11. [Interface CLI](#11-interface-cli)
12. [Mode Preview](#12-mode-preview)
13. [Structure du module](#13-structure-du-module)
14. [Pièges connus & mitigations](#14-pièges-connus--mitigations)
15. [Tests](#15-tests)

---

## 1. Vue d'ensemble

### 1.1 Mission

Prendre la vidéo **déjà montée** par l'Agent #3 (`montage_rendu.mp4`) et les métadonnées d'édition (`edit_metadata.json`), et produire une vidéo avec une bande-son complète : voix nettoyée et compressée, musique de fond adaptée au mood, effets sonores placés intelligemment sur les moments clés, le tout mixé avec ducking automatique.

### 1.2 Entrées / Sorties

```
Entrées :
  ├── montage_rendu.mp4           ← Agent #3  (vidéo montée, piste audio originale présente)
  ├── edit_metadata.json          ← Agent #3  (timings, mood, speech_segments, scene_changes)
  ├── transcript.json             ← Agent #1  (segments parole/silence pour ducking)
  ├── config.yaml                 ← Agent #6  (paramètres audio : ducking_level, volumes)
  └── .env                        ← Agent #6  (clés API Epidemic Sound, etc.)

Sorties :
  ├── montage_audio.mp4               (vidéo avec bande-son finale)
  ├── montage_audio_stems/            (pistes séparées pour débogage)
  │   ├── voice_cleaned.wav
  │   ├── music_background.wav
  │   ├── sfx_master.wav
  │   └── master_mix.wav
  └── audio_metadata.json             (métadonnées pour Agent #5)
```

### 1.3 Stack technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11+ | Orchestrateur, logique métier |
| Pydantic | 2.7+ | Schémas de config & modèles audio |
| FFmpeg | 7.0+ | Extraction/ré-échantillonnage audio, filtres (volume, sidechain, aresample) |
| ffmpeg-python | latest | Wrapper Python pour FFmpeg |
| librosa | 2.x | Analyse audio (BPM, rms, silence detection) |
| numpy | 1.26+ | Manipulation de tableaux audio |
| soundfile / audioread | latest | Lecture/écriture WAV haute qualité |
| pydub | 0.25+ | Manipulation audio simple (crossfade, silence) |
| httpx | 0.27+ | Client HTTP pour Epidemic Sound MCP |
| typer | 0.9+ | Interface CLI |

---

## 2. Architecture du module

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent #4 Orchestrator                           │
│  (orchestrator.py)                                                   │
│  Charge config, edit_metadata, transcript → pilote le pipeline     │
└───┬───────────┬───────────┬──────────┬──────────┬───────────────────┘
    │           │           │          │          │
    ▼           ▼           ▼          ▼          ▼
┌────────┐ ┌───────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐
│Voice   │ │Epidemic   │ │SFX     │ │Ducking │ │Master Export     │
│Pipeline│ │Sound MCP  │ │Engine  │ │Engine  │ │ + Sync Guard     │
│nettoy. │ │cherche    │ │place   │ │duck    │ │                  │
│compress│ │musique    │ │SFX     │ │voice/  │ │→ WAV + mux MP4  │
│EQ      │ │+ SFX by  │ │timing  │ │music   │ │→ audio_metadata  │
└────────┘ │concept    │ └────────┘ └────────┘ └──────────────────┘
           └───────────┘
```

### 2.1 Flux de données détaillé

```
edit_metadata.json + transcript.json + config.yaml + montage_rendu.mp4
    │
    ▼
┌──────────────────────────────────────┐
│ Parse & Validate                     │ ← Pydantic models
│ edit_metadata, transcript, config    │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Étape 1 : Voice Pipeline             │
│ 1a. Extraire piste audio de la vidéo │ ← FFmpeg
│ 1b. Nettoyage (gate, noise reduction)│ ← FFmpeg afftdn / sox
│ 1c. Compression (voice)              │ ← FFmpeg acompressor
│ 1d. EQ parlé (high-pass + presence)  │ ← FFmpeg equalizer
│ 1e. Normalisation (RMS -16 LUFS)    │ ← FFmpeg loudnorm
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Étape 2 : Epidemic Sound MCP         │
│ 2a. Analyser le mood/pace du montage │ ← edit_metadata.mood
│ 2b. Construire requête MCP           │ ← mood, durée, bpm, genre
│ 2c. Appeler l'API Epidemic Sound     │ ← httpx
│ 2d. Sélectionner meilleure musique   │ ← score de matching
│ 2e. Télécharger les stems WAV        │ ← streaming download
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Étape 3 : SFX Engine                 │
│ 3a. Analyser les moments clés        │ ← scene_changes, transitions
│ 3b. Suggérer des SFX par concept     │ ← basé sur le contenu parlé
│ 3c. Chercher les SFX via MCP         │ ← Epidemic Sound SFX search
│ 3d. Télécharger et tronquer          │ ← durée adaptée
│ 3e. Placer sur la timeline           │ ← alignement temporel
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Étape 4 : Ducking Engine             │
│ 4a. Charger speech_segments          │ ← edit_metadata.speech_segments
│ 4b. Construire la courbe de ducking  │ ← automations volume
│ 4c. Appliquer ducking sur musique    │ ← sidechain compression FFmpeg
│ 4d. Ajuster les fades (entrée/sortie)│ ← crossfade
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Étape 5 : Master Export              │
│ 5a. Mixer les 3 pistes (voice, music,│ ← FFmpeg amix
│     sfx) avec volumes config         │
│ 5b. Limiter (true peak -1 dB)        │ ← FFmpeg alimiter
│ 5c. Vérifier sync avec vidéo         │ ← SyncGuard
│ 5d. Mux l'audio final dans la vidéo  │ ← FFmpeg replace audio
│ 5e. Générer les stems pour debug     │ ← stems individuels
│ 5f. Sauvegarder audio_metadata.json  │ ← Pydantic serialize
└──────┬───────────────────────────────┘
       │
       ▼
  montage_audio.mp4
  audio_metadata.json
  montage_audio_stems/
```

### 2.2 Orchestrateur

```python
class AudioPipeline:
    """Orchestre l'ensemble du pipeline de design audio."""

    async def run(
        self,
        montage_video: Path,
        edit_metadata_path: Path,
        transcript_path: Path,
        config: AudioConfig,
        mode: Literal["preview", "final"] = "final",
    ) -> AudioReport:
        # 1. Parse inputs
        edit_meta = self._load_edit_metadata(edit_metadata_path)
        transcript = self._load_transcript(transcript_path)

        # 2. Voice pipeline
        voice_wav = await self._run_voice_pipeline(
            montage_video, config
        )

        # 3. Epidemic Sound search
        music_track = await self._search_and_download_music(
            edit_meta, config
        )

        # 4. SFX placement
        sfx_tracks = await self._run_sfx_engine(
            montage_video, edit_meta, transcript, config
        )

        # 5. Ducking
        music_ducked = await self._apply_ducking(
            music_track, edit_meta.speech_segments, config
        )

        # 6. Master mix
        final_audio = await self._master_mix(
            voice_wav, music_ducked, sfx_tracks, config
        )

        # 7. Sync guard
        sync_ok = await self._verify_sync(montage_video, final_audio, config)
        if not sync_ok:
            raise AudioSyncError("Audio out of sync after mix")

        # 8. Mux into video
        output_video = await self._mux_audio_into_video(
            montage_video, final_audio, config
        )

        # 9. Build report
        return self._build_report(
            output_video, voice_wav, music_track, sfx_tracks, final_audio, config
        )
```

---

## 3. Pipeline d'exécution

### 3.1 Gestion des étapes

Chaque étape est un module indépendant avec :
- Entrée/sortie typée (Pydantic + chemins de fichiers)
- Gestion d'erreur → fallback ou crash explicite
- Cache des fichiers temporaires dans `config.cache_dir`
- Logging structuré (JSON lines)

### 3.2 Modes d'exécution

| Mode | Usage | Optimisations |
|------|-------|---------------|
| `final` | Production complète | Tout le pipeline, qualité max |
| `preview` | Itération rapide | SFX simplifiés, ducking basique, pas de stem exports |
| `voice_only` | Test voix uniquement | Skip musique + SFX |
| `dry_run` | Planification seule | Ne produit que le plan audio + suggestions SFX |

### 3.3 Communication avec l'Agent #3

L'Agent #4 reçoit de l'Agent #3 :
- `montage_rendu.mp4` : vidéo montée avec piste audio originale encore présente
- `edit_metadata.json` : structuré selon `EditMetadata` (timings, mood, speech_segments, scene_changes, pace, bpm_estimate)

L'Agent #4 envoie à l'Agent #5 :
- `montage_audio.mp4` : vidéo avec bande-son finale
- `audio_metadata.json` : structuré selon `AudioMetadata`
- `montage_audio_stems/` : pistes séparées pour analyse qualité

---

## 4. Modèles de données (Pydantic)

### 4.1 AudioConfig — Configuration audio chargée du YAML

```python
# shared/schemas/audio.py
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional
from pathlib import Path


class AudioConfig(BaseModel):
    """Configuration complète du pipeline audio."""

    # ── Ducking ──────────────────────────────────────────────
    ducking_enabled: bool = True
    ducking_level: float = Field(
        default=-12.0, ge=-40.0, le=0.0,
        description="Réduction de volume musique pendant parole (dB)"
    )
    ducking_attack: float = Field(
        default=0.05, ge=0.01, le=1.0,
        description="Temps d'attaque du ducking en secondes"
    )
    ducking_release: float = Field(
        default=0.30, ge=0.05, le=3.0,
        description="Temps de release du ducking en secondes"
    )
    ducking_threshold: float = Field(
        default=-20.0, ge=-60.0, le=0.0,
        description="Seuil de déclenchement du ducking (dBFS)"
    )

    # ── Volumes ──────────────────────────────────────────────
    voice_volume: float = Field(
        default=0.0, ge=-20.0, le=6.0,
        description="Volume voix relatif au master (dB)"
    )
    music_volume: float = Field(
        default=-6.0, ge=-40.0, le=6.0,
        description="Volume musique relatif au master (dB)"
    )
    sfx_volume: float = Field(
        default=-3.0, ge=-30.0, le=6.0,
        description="Volume effets sonores relatif au master (dB)"
    )
    master_volume: float = Field(
        default=-1.0, ge=-6.0, le=0.0,
        description="Volume master (dB) — headroom pour le true peak limiter"
    )

    # ── Voice Processing ─────────────────────────────────────
    voice_noise_reduction: bool = True
    voice_noise_reduction_strength: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Force de la réduction de bruit (0=off, 1=max)"
    )
    voice_highpass_freq: float = Field(
        default=80.0, ge=20.0, le=200.0,
        description="Fréquence de coupure high-pass (Hz)"
    )
    voice_lowpass_freq: float = Field(
        default=8000.0, ge=4000.0, le=16000.0,
        description="Fréquence de coupure low-pass (Hz)"
    )
    voice_presence_boost: float = Field(
        default=2.0, ge=0.0, le=6.0,
        description="Boost des fréquences présence (2-6 kHz) en dB"
    )
    voice_compression_ratio: float = Field(
        default=4.0, ge=1.0, le=20.0,
        description="Ratio du compresseur vocal"
    )
    voice_compression_threshold: float = Field(
        default=-18.0, ge=-40.0, le=0.0,
        description="Seuil du compresseur vocal (dB)"
    )
    voice_normalization_target: float = Field(
        default=-16.0, ge=-23.0, le=-10.0,
        description="Cible LUFS pour la normalisation de la voix"
    )

    # ── Music ────────────────────────────────────────────────
    music_search_enabled: bool = True
    music_fade_in: float = Field(
        default=1.0, ge=0.0, le=10.0,
        description="Durée du fondu d'entrée musique (secondes)"
    )
    music_fade_out: float = Field(
        default=2.0, ge=0.0, le=10.0,
        description="Durée du fondu de sortie musique (secondes)"
    )
    music_max_duration: float = Field(
        default=300.0, ge=10.0, le=3600.0,
        description="Durée maximale de la piste musique (secondes)"
    )
    music_loop: bool = Field(
        default=False,
        description="Autoriser le looping de la musique si trop courte"
    )
    music_preferred_bpm_range: tuple[float, float] = Field(
        default=(80.0, 140.0),
        description="Plage BPM préférée pour la musique"
    )

    # ── SFX ──────────────────────────────────────────────────
    sfx_enabled: bool = True
    sfx_fade_in: float = Field(
        default=0.05, ge=0.0, le=1.0,
        description="Fondu d'entrée SFX (secondes)"
    )
    sfx_fade_out: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="Fondu de sortie SFX (secondes)"
    )
    sfx_min_interval: float = Field(
        default=0.5, ge=0.1, le=5.0,
        description="Intervalle minimum entre deux SFX (secondes)"
    )
    sfx_max_per_minute: int = Field(
        default=6, ge=1, le=30,
        description="Nombre max d'SFX par minute"
    )
    sfx_auto_generate: bool = Field(
        default=True,
        description="Générer automatiquement les suggestions SFX"
    )
    sfx_concepts: list[str] = Field(
        default_factory=list,
        description="Liste de concepts SFX forcés (ex: ['whoosh', 'click', 'transition'])"
    )

    # ── Master Export ────────────────────────────────────────
    export_stems: bool = Field(
        default=True,
        description="Exporter les pistes séparées (voice, music, sfx)"
    )
    export_bit_depth: Literal[16, 24, 32] = Field(
        default=24, description="Bits par échantillon pour l'export"
    )
    export_sample_rate: int = Field(
        default=48000, ge=44100, le=192000,
        description="Fréquence d'échantillonnage d'export"
    )
    export_codec: Literal["aac", "mp3", "pcm_s16le"] = Field(
        default="aac", description="Codec audio vidéo finale"
    )
    export_bitrate: str = Field(
        default="192k", description="Bitrate export audio vidéo"
    )
    true_peak_limit: float = Field(
        default=-1.0, ge=-3.0, le=0.0,
        description="Limiteur true peak (dB)"
    )

    # ── Sync ─────────────────────────────────────────────────
    sync_tolerance_ms: float = Field(
        default=40.0, ge=10.0, le=200.0,
        description="Tolérance de désync audio/vidéo (ms)"
    )
    sync_auto_correct: bool = Field(
        default=True,
        description="Corriger automatiquement la désync"
    )

    # ── Paths ────────────────────────────────────────────────
    work_dir: str = Field(
        default="/tmp/agent4_cache",
        description="Dossier de travail temporaire"
    )
    cache_dir: str = Field(
        default="/tmp/agent4_cache",
        description="Cache des fichiers temporaires"
    )
    stems_dir: str = Field(
        default="montage_audio_stems",
        description="Dossier d'export des stems"
    )

    # ── Epidemic Sound ───────────────────────────────────────
    epidemic_sound_api_key: Optional[str] = Field(
        default=None,
        description="Clé API Epidemic Sound (lecture depuis .env)"
    )
    epidemic_sound_base_url: str = Field(
        default="https://mcp.epidemicsound.com/api",
        description="URL de base de l'API MCP Epidemic Sound"
    )
    epidemic_sound_timeout: int = Field(
        default=30, ge=5, le=120,
        description="Timeout pour les appels API (secondes)"
    )

    @model_validator(mode="after")
    def validate_volumes(self):
        """Vérifie la cohérence des volumes."""
        if self.music_volume > self.voice_volume:
            # La musique ne devrait pas être plus forte que la voix
            import warnings
            warnings.warn(
                "music_volume > voice_volume peut enterrer la voix. "
                "Vérifiez vos réglages."
            )
        return self

    @property
    def stems_path(self) -> Path:
        return Path(self.stems_dir)

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir)
```

### 4.2 SoundEffect — Un effet sonore placé sur la timeline

```python
class SoundEffect(BaseModel):
    """Effet sonore unique placé sur la timeline."""

    id: str = Field(
        ..., description="Identifiant unique (ex: 'sfx_0001')"
    )
    concept: str = Field(
        ..., description="Concept / description de l'effet (ex: 'whoosh_transition')"
    )
    category: Literal[
        "transition",       # Whoosh, swoosh pour transitions
        "accent",           # Impact, hit pour moments forts
        "atmosphere",       # Ambiance, room tone
        "ui",               # Clic, ping, notification
        "text_reveal",      # Texte qui apparaît
        "nature",           # Oiseaux, vent, eau
        "urban",            # Ville, traffic, foule
        "tech",             # Ordinateur, clavier, beep
        "cinematic",        # Whoosh large, riser, braam
        "custom",           # Personnalisé via config
    ] = Field(..., description="Catégorie de l'effet")

    source: str = Field(
        ..., description="Source : 'epidemic_sound', 'generated', 'library'"
    )
    epidemic_id: Optional[str] = Field(
        default=None,
        description="ID Epidemic Sound si applicable"
    )
    local_path: Optional[str] = Field(
        default=None,
        description="Chemin local du fichier audio téléchargé"
    )

    # Timing
    start_time: float = Field(
        ..., ge=0.0,
        description="Timecode de déclenchement dans la vidéo (secondes)"
    )
    duration: float = Field(
        ..., ge=0.05, le=30.0,
        description="Durée de l'effet (secondes)"
    )
    end_time: float = Field(
        ..., ge=0.0,
        description="Fin calculée = start_time + duration"
    )

    # Mix
    volume_db: float = Field(
        default=0.0, ge=-30.0, le=6.0,
        description="Volume relatif de l'effet (dB)"
    )
    pan: float = Field(
        default=0.0, ge=-1.0, le=1.0,
        description="Panoramique (-1=gauche, 0=centre, 1=droite)"
    )
    fade_in: float = Field(
        default=0.05, ge=0.0, le=1.0,
        description="Fondu d'entrée (secondes)"
    )
    fade_out: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="Fondu de sortie (secondes)"
    )

    # Métadonnées
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Score de pertinence du placement (0-1)"
    )
    auto_generated: bool = Field(
        default=True,
        description="True = généré automatiquement, False = forcé par config"
    )

    @model_validator(mode="after")
    def compute_end_time(self):
        self.end_time = self.start_time + self.duration
        return self
```

### 4.3 MusicTrack — Piste musicale

```python
class MusicTrack(BaseModel):
    """Piste musicale de fond."""

    id: str = Field(..., description="Identifiant unique (ex: 'music_0001')")
    title: str = Field(..., description="Titre du morceau")
    artist: str = Field(default="", description="Artiste / compositeur")

    # Source
    source: Literal["epidemic_sound", "library", "generated", "none"] = Field(
        ..., description="Source de la musique"
    )
    epidemic_id: Optional[str] = Field(
        default=None, description="ID Epidemic Sound"
    )
    epidemic_url: Optional[str] = Field(
        default=None, description="URL Epidemic Sound"
    )
    local_path: Optional[str] = Field(
        default=None, description="Chemin local du fichier téléchargé"
    )

    # Caractéristiques musicales
    bpm: Optional[float] = Field(
        default=None, ge=20.0, le=300.0,
        description="Tempo en BPM"
    )
    key: Optional[str] = Field(
        default=None, description="Tonalité (ex: 'C major', 'A minor')"
    )
    mood: list[str] = Field(
        default_factory=list,
        description="Humeurs associées (ex: ['energetic', 'uplifting'])"
    )
    genres: list[str] = Field(
        default_factory=list,
        description="Genres musicaux"
    )
    duration: float = Field(
        ..., ge=1.0, description="Durée totale du morceau (secondes)"
    )

    # Timeline placement
    start_time: float = Field(
        default=0.0, ge=0.0,
        description="Début dans la vidéo (secondes)"
    )
    end_time: float = Field(
        ..., ge=0.0,
        description="Fin dans la vidéo (secondes, peut être < duration si loop)"
    )
    loop_count: int = Field(
        default=1, ge=1, le=100,
        description="Nombre de boucles si la musique est plus courte que la vidéo"
    )

    # Mix
    volume_db: float = Field(
        default=-6.0, ge=-40.0, le=6.0,
        description="Volume de base (dB)"
    )
    ducking_applied: bool = Field(
        default=False,
        description="True si le ducking a été appliqué"
    )
    fade_in: float = Field(
        default=1.0, ge=0.0, le=10.0,
        description="Fondu d'entrée (secondes)"
    )
    fade_out: float = Field(
        default=2.0, ge=0.0, le=10.0,
        description="Fondu de sortie (secondes)"
    )

    # Métriques de matching
    match_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Score de matching avec le mood du montage"
    )
    match_reason: str = Field(
        default="",
        description="Raison textuelle du choix"
    )
```

### 4.4 AudioMix — Configuration de mixage complète

```python
class AudioMix(BaseModel):
    """Configuration de mixage complète pour une vidéo."""

    # Timing global
    total_duration: float = Field(
        ..., ge=0.0, description="Durée totale de la vidéo (secondes)"
    )

    # Pistes
    voice: dict = Field(
        default_factory=lambda: {
            "path": None,          # Chemin WAV traité
            "volume_db": 0.0,
            "processed": False,
            "peaks": [],
        },
        description="Piste vocale",
    )
    music: Optional[MusicTrack] = Field(
        default=None, description="Piste musicale"
    )
    sfx: list[SoundEffect] = Field(
        default_factory=list, description="Effets sonores"
    )

    # Ducking
    ducking_curve: list[dict] = Field(
        default_factory=list,
        description="Courbe de ducking : [{time, gain_db}, ...]",
    )
    speech_segments: list[dict] = Field(
        default_factory=list,
        description="Segments de parole [{start, end, text}] pour le ducking",
    )

    # Master
    master_volume_db: float = Field(
        default=-1.0, description="Volume master (dB)"
    )
    true_peak_limit: float = Field(
        default=-1.0, description="Limite true peak (dB)"
    )
    loudness_target: float = Field(
        default=-14.0, description="Cible LUFS intégrée"
    )

    # Chemins
    output_mix_path: Optional[str] = Field(
        default=None, description="Chemin du fichier mixé final (WAV)"
    )
    output_video_path: Optional[str] = Field(
        default=None, description="Chemin de la vidéo avec audio final (MP4)"
    )
    stems_dir: Optional[str] = Field(
        default=None, description="Dossier contenant les stems"
    )
```

### 4.5 AudioMetadata — Métadonnées de sortie pour Agent #5

```python
class AudioMetadata(BaseModel):
    """Métadonnées de la piste audio finale — sortie vers Agent #5."""

    schema_version: str = Field(default="2.0")
    source_edit: str = Field(..., description="Chemin montage source")
    source_video: str = Field(..., description="Chemin vidéo finale")

    # Tracks
    tracks: list[dict] = Field(
        ...,
        description="Toutes les pistes audio utilisées",
    )

    # Metrics
    master_volume_db: float = Field(..., description="Volume master (dB)")
    peak_level_db: float = Field(..., description="Pic de niveau (dB)")
    rms_level_db: float = Field(..., description="Niveau RMS moyen (dB)")
    loudness_lufs: float = Field(
        ..., description="Loudness intégré (LUFS) — norme EBU R128"
    )
    loudness_range: float = Field(
        default=0.0, description="Loudness range (LU) — dynamique"
    )
    true_peak: float = Field(
        default=0.0, description="True peak (dBTP)"
    )

    # Music info
    music_epidemic_id: Optional[str] = Field(default=None)
    music_title: Optional[str] = Field(default=None)
    music_artist: Optional[str] = Field(default=None)
    music_bpm: Optional[float] = Field(default=None)
    music_key: Optional[str] = Field(default=None)
    music_mood: list[str] = Field(default_factory=list)
    music_match_score: float = Field(default=0.0)

    # SFX stats
    sfx_count: int = Field(default=0, description="Nombre d'effets sonores")
    sfx_categories: dict[str, int] = Field(
        default_factory=dict,
        description="Répartition par catégorie : {'transition': 5, 'accent': 3}",
    )

    # Process info
    ducking_applied: bool = Field(default=False)
    ducking_level_db: float = Field(default=0.0)
    voice_processing: dict = Field(
        default_factory=lambda: {
            "noise_reduction": False,
            "compression": False,
            "eq": False,
            "normalization": False,
        }
    )
    sync_offset_ms: float = Field(
        default=0.0,
        description="Offset audio/vidéo final (ms, idéalement < 40ms)"
    )
    sync_ok: bool = Field(
        default=True,
        description="True si sync dans la tolérance"
    )

    # Pipeline
    pipeline_duration_ms: float = Field(
        default=0.0,
        description="Temps total d'exécution du pipeline audio"
    )
    errors: list[str] = Field(
        default_factory=list, description="Erreurs non-bloquantes"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Avertissements"
    )
```

### 4.6 Schémas internes supplémentaires

```python
class SpeechSegmentForDucking(BaseModel):
    """Segment de parole utilisé par l'algorithme de ducking."""
    start: float = Field(..., description="Début de la parole (s)")
    end: float = Field(..., description="Fin de la parole (s)")
    text: str = Field(default="", description="Texte parlé")
    volume_estimate: float = Field(
        default=0.0,
        description="Estimation du volume RMS du segment"
    )


class DuckingFrame(BaseModel):
    """Point de la courbe de ducking à une frame donnée."""
    time: float = Field(..., description="Timecode (secondes)")
    gain_db: float = Field(
        ..., description="Gain à appliquer (dB) — négatif = réduction"
    )


class EpidemicSearchQuery(BaseModel):
    """Requête de recherche Epidemic Sound MCP."""
    query: str = Field(..., description="Texte de recherche")
    mood: Optional[list[str]] = Field(default=None, description="Humeurs")
    genre: Optional[list[str]] = Field(default=None, description="Genres")
    bpm_min: Optional[float] = Field(default=None)
    bpm_max: Optional[float] = Field(default=None)
    duration_min: Optional[float] = Field(default=None)
    duration_max: Optional[float] = Field(default=None)
    type: Literal["music", "sfx"] = Field(default="music")
    limit: int = Field(default=10, ge=1, le=50)
    page: int = Field(default=1, ge=1)
    sort_by: Literal["relevance", "popularity", "date"] = Field(
        default="relevance"
    )


class EpidemicSearchResult(BaseModel):
    """Résultat de recherche Epidemic Sound."""
    id: str = Field(..., description="ID unique du morceau/SFX")
    title: str
    artist: Optional[str] = None
    duration: float
    bpm: Optional[float] = None
    key: Optional[str] = None
    moods: list[str] = []
    genres: list[str] = []
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    waveform_url: Optional[str] = None
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)


class AudioReport(BaseModel):
    """Rapport de sortie du pipeline audio (log interne)."""
    pipeline_version: str = "4.0.0"
    source_video: str
    total_duration: float
    voice_processed: bool
    music_track: Optional[MusicTrack] = None
    music_applied: bool
    sfx_count: int
    sfx_list: list[str] = []  # Concepts utilisés
    ducking_applied: bool
    ducking_curve_points: int = 0
    sync_offset_ms: float
    sync_ok: bool
    loudness_lufs: float
    true_peak_db: float
    render_mode: str
    total_render_time_ms: float
    output_path: str
    stems_path: Optional[str] = None
    errors: list[str] = []
    warnings: list[str] = []
```

---

## 5. Configuration externalisable

### 5.1 Fichier `config.yaml`

Fichier chargé par l'Orchestrator (Agent #6) et passé à l'Agent #4 :

```yaml
audio:
  # ── Ducking ──────────────────────────────────────────────
  ducking_enabled: true
  ducking_level: -12.0           # dB de réduction musique pendant parole
  ducking_attack: 0.05           # secondes
  ducking_release: 0.30          # secondes
  ducking_threshold: -20.0       # dBFS seuil de déclenchement

  # ── Volumes ──────────────────────────────────────────────
  voice_volume: 0.0              # dB relatif au master
  music_volume: -6.0             # dB relatif au master
  sfx_volume: -3.0              # dB relatif au master
  master_volume: -1.0            # dB (headroom pour limiter)

  # ── Voice Processing ─────────────────────────────────────
  voice_noise_reduction: true
  voice_noise_reduction_strength: 0.3
  voice_highpass_freq: 80.0      # Hz
  voice_lowpass_freq: 8000.0     # Hz
  voice_presence_boost: 2.0      # dB
  voice_compression_ratio: 4.0
  voice_compression_threshold: -18.0
  voice_normalization_target: -16.0  # LUFS

  # ── Music ────────────────────────────────────────────────
  music_search_enabled: true
  music_fade_in: 1.0             # secondes
  music_fade_out: 2.0            # secondes
  music_max_duration: 300        # secondes (5 min max)
  music_loop: false
  music_preferred_bpm_range: [80, 140]

  # ── SFX ──────────────────────────────────────────────────
  sfx_enabled: true
  sfx_fade_in: 0.05
  sfx_fade_out: 0.15
  sfx_min_interval: 0.5
  sfx_max_per_minute: 6
  sfx_auto_generate: true
  sfx_concepts: []               # Concepts forcés (ex: ["whoosh", "click"])

  # ── Master Export ────────────────────────────────────────
  export_stems: true
  export_bit_depth: 24
  export_sample_rate: 48000
  export_codec: "aac"
  export_bitrate: "192k"
  true_peak_limit: -1.0          # dBTP

  # ── Sync ─────────────────────────────────────────────────
  sync_tolerance_ms: 40.0
  sync_auto_correct: true

  # ── Paths ────────────────────────────────────────────────
  work_dir: "/tmp/agent4_cache"
  stems_dir: "montage_audio_stems"

  # ── Epidemic Sound ───────────────────────────────────────
  epidemic_sound_base_url: "https://mcp.epidemicsound.com/api"
  epidemic_sound_timeout: 30
```

### 5.2 Validation Pydantic

```python
class AudioConfigValidator(BaseModel):
    """Validateur pour le fichier config.yaml section audio."""
    audio: AudioConfig

    @model_validator(mode="after")
    def check_env_api_key(self):
        """Vérifie que la clé API Epidemic Sound est disponible."""
        if self.audio.music_search_enabled or self.audio.sfx_enabled:
            if not self.audio.epidemic_sound_api_key:
                # Tentative de lecture depuis l'environnement
                import os
                key = os.environ.get("EPIDEMIC_SOUND_API_KEY")
                if not key:
                    raise ValueError(
                        "EPIDEMIC_SOUND_API_KEY manquante. "
                        "Définissez-la dans config.yaml ou dans .env"
                    )
                self.audio.epidemic_sound_api_key = key
        return self
```

### 5.3 Fichier `.env`

```
# Obligatoire si music_search_enabled ou sfx_enabled
EPIDEMIC_SOUND_API_KEY=sk_epidemic_xxxxx

# Optionnel
AGENT4_WORK_DIR=/tmp/agent4_cache
AGENT4_EXPORT_CODEC=aac
```

---

## 6. MCP Epidemic Sound

### 6.1 Architecture du client MCP

```
┌──────────────────────────────────────────────┐
│            EpidemicSoundMCPClient             │
│  (epidemic_client.py)                         │
├──────────────────────────────────────────────┤
│                                                │
│  search_music(query, mood, bpm)               │
│      → list[EpidemicSearchResult]              │
│                                                │
│  search_sfx(concept, duration)                 │
│      → list[EpidemicSearchResult]              │
│                                                │
│  download_track(track_id, output_path)         │
│      → Path (fichier WAV téléchargé)           │
│                                                │
│  get_track_info(track_id)                      │
│      → EpidemicSearchResult (complet)          │
│                                                │
│  get_mood_suggestions(concept)                 │
│      → list[str] (moods suggérées)             │
└──────────────────────────────────────────────┘
```

### 6.2 Endpoints MCP

L'API MCP Epidemic Sound expose les endpoints REST suivants :

| Méthode | Endpoint | Description | Paramètres |
|---------|----------|-------------|------------|
| `GET` | `/search` | Recherche musique/SFX | `q`, `mood`, `genre`, `bpm_min`, `bpm_max`, `duration_min`, `duration_max`, `type`, `limit`, `page` |
| `GET` | `/tracks/{id}` | Infos détaillées d'un morceau | — |
| `GET` | `/tracks/{id}/download` | URL de téléchargement | `format` (wav, mp3) |
| `GET` | `/categories/{type}` | Catégories disponibles | `type` (music, sfx) |
| `GET` | `/moods` | Liste des moods disponibles | — |

### 6.3 Client MCP — Implémentation

```python
class EpidemicSoundMCPClient:
    """
    Client MCP pour l'API Epidemic Sound.

    Recherche et télécharge des musiques / effets sonores libres de droits
    par concept, durée, humeur, BPM, etc.

    Documentation MCP : https://mcp.epidemicsound.com/docs
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://mcp.epidemicsound.com/api",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    # ── Search ──────────────────────────────────────────────

    async def search_music(
        self,
        query: str,
        mood: Optional[list[str]] = None,
        genre: Optional[list[str]] = None,
        bpm_min: Optional[float] = None,
        bpm_max: Optional[float] = None,
        duration_min: Optional[float] = None,
        duration_max: Optional[float] = None,
        limit: int = 10,
        page: int = 1,
    ) -> list[EpidemicSearchResult]:
        """
        Recherche de musique par concept, mood, BPM, durée.

        Stratégie de requête :
        - Si mood connu : chercher par mood d'abord
        - Si BPM connu : filtrer par plage BPM
        - Si concept : chercher par mots-clés
        - Combiner les filtres pour affiner
        """
        params = {
            "q": query,
            "type": "music",
            "limit": min(limit, 50),
            "page": page,
        }

        if mood:
            params["mood"] = ",".join(mood)
        if genre:
            params["genre"] = ",".join(genre)
        if bpm_min is not None:
            params["bpm_min"] = bpm_min
        if bpm_max is not None:
            params["bpm_max"] = bpm_max
        if duration_min is not None:
            params["duration_min"] = duration_min
        if duration_max is not None:
            params["duration_max"] = duration_max

        resp = await self.client.get("/search", params=params)
        resp.raise_for_status()
        data = resp.json()

        return [
            self._parse_result(item) for item in data.get("results", [])
        ]

    async def search_sfx(
        self,
        concept: str,
        duration_min: Optional[float] = None,
        duration_max: Optional[float] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[EpidemicSearchResult]:
        """
        Recherche d'effets sonores par concept et durée.

        Typiquement utilisé pour :
        - "whoosh" (transitions, 0.3-1.0s)
        - "click" (UI, 0.1-0.3s)
        - "impact" (accents, 0.5-2.0s)
        - "ambiance" (atmosphère, 5-30s)
        """
        params = {
            "q": concept,
            "type": "sfx",
            "limit": min(limit, 50),
        }

        if duration_min is not None:
            params["duration_min"] = duration_min
        if duration_max is not None:
            params["duration_max"] = duration_max
        if category:
            params["category"] = category

        resp = await self.client.get("/search", params=params)
        resp.raise_for_status()
        data = resp.json()

        return [
            self._parse_result(item) for item in data.get("results", [])
        ]

    # ── Download ────────────────────────────────────────────

    async def download_track(
        self,
        track_id: str,
        output_path: Path,
        format: str = "wav",
    ) -> Path:
        """
        Télécharge un morceau/SFX depuis Epidemic Sound.

        Étapes :
        1. Récupérer l'URL de téléchargement via GET /tracks/{id}/download
        2. Streamer le fichier vers output_path
        3. Retourner le chemin local
        """
        resp = await self.client.get(
            f"/tracks/{track_id}/download",
            params={"format": format},
        )
        resp.raise_for_status()
        download_url = resp.json()["download_url"]

        # Streaming download
        async with httpx.AsyncClient() as dl_client:
            async with dl_client.stream("GET", download_url) as dl_resp:
                dl_resp.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    async for chunk in dl_resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        return output_path

    # ── Info ────────────────────────────────────────────────

    async def get_track_info(self, track_id: str) -> EpidemicSearchResult:
        """Récupère les informations détaillées d'un morceau."""
        resp = await self.client.get(f"/tracks/{track_id}")
        resp.raise_for_status()
        return self._parse_result(resp.json())

    async def get_mood_suggestions(
        self, concept: str
    ) -> list[str]:
        """
        Suggestions de moods pour un concept donné.

        Exemple :
            concept="tutorial coding" → ["focused", "uplifting", "modern"]
            concept="action gameplay"  → ["energetic", "intense", "cinematic"]
        """
        resp = await self.client.get(
            "/moods/suggestions",
            params={"q": concept},
        )
        resp.raise_for_status()
        return resp.json().get("moods", [])

    # ── Helpers ─────────────────────────────────────────────

    async def select_best_match(
        self,
        results: list[EpidemicSearchResult],
        target_mood: str,
        target_bpm: Optional[float] = None,
        target_duration: float = 60.0,
    ) -> Optional[EpidemicSearchResult]:
        """
        Sélectionne le meilleur résultat selon :
        - Matching de mood
        - Proximité BPM
        - Durée (assez long pour couvrir le montage)
        - Popularité

        Retourne le meilleur résultat ou None.
        """
        if not results:
            return None

        scored = []
        for r in results:
            score = 0.0

            # Mood matching (poids 0.4)
            mood_score = self._score_mood_match(r.moods, target_mood)
            score += 0.4 * mood_score

            # BPM proximity (poids 0.3)
            bpm_score = self._score_bpm_match(r.bpm, target_bpm)
            score += 0.3 * bpm_score

            # Duration adequacy (poids 0.2)
            duration_score = self._score_duration_match(
                r.duration, target_duration
            )
            score += 0.2 * duration_score

            # Popularity (poids 0.1)
            # (non implémenté, fallback 0.5)
            score += 0.1 * 0.5

            r.match_score = min(score, 1.0)
            scored.append(r)

        scored.sort(key=lambda x: x.match_score, reverse=True)
        return scored[0] if scored[0].match_score > 0.3 else None

    @staticmethod
    def _score_mood_match(
        track_moods: list[str], target_mood: str
    ) -> float:
        """Score de matching entre les moods du track et le mood cible."""
        if not track_moods or not target_mood:
            return 0.5
        target_lower = target_mood.lower()
        mood_keywords = target_lower.replace("_", " ").split()

        matches = sum(
            1 for m in track_moods
            if any(kw in m.lower() for kw in mood_keywords)
        )
        return min(matches / max(len(mood_keywords), 1), 1.0)

    @staticmethod
    def _score_bpm_match(
        track_bpm: Optional[float], target_bpm: Optional[float]
    ) -> float:
        """Score de proximité BPM (1.0 = parfait)."""
        if track_bpm is None or target_bpm is None:
            return 0.5
        ratio = abs(track_bpm - target_bpm) / max(target_bpm, 1)
        return max(0.0, 1.0 - ratio)

    @staticmethod
    def _score_duration_match(
        track_duration: float, target_duration: float
    ) -> float:
        """Score de correspondance de durée."""
        if track_duration >= target_duration:
            return 1.0  # Assez long
        # Si trop court, score réduit proportionnellement
        return max(0.0, track_duration / target_duration)

    @staticmethod
    def _parse_result(data: dict) -> EpidemicSearchResult:
        """Parse une réponse JSON en EpidemicSearchResult."""
        return EpidemicSearchResult(
            id=data.get("id", ""),
            title=data.get("title", ""),
            artist=data.get("artist"),
            duration=data.get("duration", 0.0),
            bpm=data.get("bpm"),
            key=data.get("key"),
            moods=data.get("moods", []),
            genres=data.get("genres", []),
            preview_url=data.get("preview_url"),
            download_url=data.get("download_url"),
            waveform_url=data.get("waveform_url"),
        )
```

### 6.4 Stratégie de sélection musicale

```
┌──────────────────────┐
│ edit_metadata.json    │
│  .mood = "energetic"  │
│  .pace = "fast"       │
│  .beat_per_minute = 128│
│  .duration = 94.64    │
└──────────┬───────────┘
           ▼
┌──────────────────────────────────────┐
│ Mood Analyzer                         │
│                                       │
│ Mapping mood → Epidemic moods :      │
│   "energetic" → ["energetic",        │
│                   "upbeat",           │
│                   "powerful",         │
│                   "driving"]          │
│   "calm" → ["calm", "peaceful",      │
│              "ambient", "soft"]       │
│   "professional" → ["corporate",     │
│                      "modern",        │
│                      "inspiring",     │
│                      "focused"]       │
│   "educational" → ["uplifting",      │
│                     "focused",        │
│                     "warm",           │
│                     "gentle"]         │
│   "dramatic" → ["cinematic",         │
│                  "suspenseful",       │
│                  "epic",             │
│                  "intense"]           │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ Construire EpidemicSearchQuery :     │
│   query = "energetic tutorial tech"  │
│   mood = ["energetic", "upbeat"]     │
│   bpm_min = 110, bpm_max = 140       │
│   duration_min = 90                  │
│   type = "music"                     │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ Appel MCP → list[EpidemicSearchResult]│
│                                      │
│ Trier par match_score                │
│ Télécharger le meilleur              │
│ Tronquer/loop à la durée du montage  │
└──────────────────────────────────────┘
```

### 6.5 Fallback — Pas d'API disponible

Si l'API Epidemic Sound est indisponible ou que la clé API est manquante :

1. **Mode dégradé silencieux** : Utiliser uniquement la piste audio originale de la vidéo montée (voix uniquement).
2. **Mode library** : Chercher dans `/data/audio/music_library/` et `/data/audio/sfx_library/` des fichiers locaux.
3. **Mode génération** : Générer des sons simples via `ffmpeg` (sine waves, noise, etc.) comme placeholder.
4. **Alerte** : Logger un warning mais ne pas bloquer le pipeline.

---

## 7. Audio Mixing Pipeline

### 7.1 Voix principale (Voice Pipeline)

#### 7.1.1 Étapes de traitement

```
montage_rendu.mp4
    │
    ▼
┌────────────────────────────┐
│ 1. Extraction audio        │ ← FFmpeg : extraire la piste audio
│    → voice_raw.wav         │   complète de la vidéo montée
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 2. Noise Gate              │ ← ffmpeg agate
│    → voice_gated.wav       │   Couper les silences < seuil
│                            │   Evite le bruit de fond constant
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 3. Noise Reduction         │ ← ffmpeg afftdn (ou sox noisered)
│    → voice_denoised.wav    │   Réduction du bruit stationnaire
│                            │   (ventilo, souffle, buzz)
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 4. High-pass Filter        │ ← ffmpeg highpass=f=80
│    → voice_hpf.wav         │   Coupe les infra-basses (< 80 Hz)
│                            │   (rumble, souffle grave)
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 5. Low-pass Filter         │ ← ffmpeg lowpass=f=8000
│    → voice_lpf.wav         │   Coupe les aigus extrêmes (> 8 kHz)
│                            │   (sifflements, bruit numérique)
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 6. Presence Boost (EQ)     │ ← ffmpeg equalizer
│    → voice_eq.wav          │   Boost 2-6 kHz pour clarté vocale
│                            │   +2 dB typique
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 7. Compression             │ ← ffmpeg acompressor
│    → voice_compressed.wav  │   Ratio 4:1, threshold -18 dB
│                            │   Lisse la dynamique vocale
└──────────┬─────────────────┘
           ▼
┌────────────────────────────┐
│ 8. Normalization (LUFS)    │ ← ffmpeg loudnorm
│    → voice_normalized.wav  │   Cible -16 LUFS (norme EBU R128)
│                            │   Volume constant entre vidéos
└──────────┬─────────────────┘
           ▼
    voice_cleaned.wav
```

#### 7.1.2 Implémentation VoicePipeline

```python
class VoicePipeline:
    """
    Traitement de la piste vocale : extraction, nettoyage, compression, EQ, normalisation.

    Workflow :
    extraire() → gate() → denoise() → highpass() → lowpass() → presence_boost() → compress() → normalize()
    """

    def __init__(self, config: AudioConfig):
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def process(
        self,
        video_path: Path,
        output_path: Path,
    ) -> Path:
        """Exécute le pipeline vocal complet."""
        # 1. Extraire l'audio de la vidéo
        raw = await self._extract_from_video(video_path)

        # 2. Noise gate
        gated = await self._apply_gate(raw)

        # 3. Noise reduction
        if self.config.voice_noise_reduction:
            denoised = await self._apply_noise_reduction(gated)
        else:
            denoised = gated

        # 4. High-pass filter
        hpf = await self._apply_highpass(denoised)

        # 5. Low-pass filter
        lpf = await self._apply_lowpass(hpf)

        # 6. Presence boost
        eq = await self._apply_presence_boost(lpf)

        # 7. Compression
        compressed = await self._apply_compression(eq)

        # 8. Normalization
        normalized = await self._apply_normalization(compressed, output_path)

        return normalized

    async def _extract_from_video(self, video_path: Path) -> Path:
        """Extraction de la piste audio depuis la vidéo."""
        output = self.cache_dir / "voice_raw.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",                          # Pas de vidéo
            "-acodec", "pcm_s16le",         # WAV 16-bit
            "-ar", str(self.config.export_sample_rate),
            "-ac", "2",                     # Stéréo
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_gate(self, input_path: Path) -> Path:
        """Noise gate : coupe les silences sous le seuil."""
        output = self.cache_dir / "voice_gated.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", f"agate=threshold=-35dB:range=20dB:ratio=10:attack=5:release=50",
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_noise_reduction(self, input_path: Path) -> Path:
        """Réduction de bruit via FFmpeg afftdn."""
        output = self.cache_dir / "voice_denoised.wav"
        strength = self.config.voice_noise_reduction_strength
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", f"afftdn=nf={-25 + 30 * strength}",
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_highpass(self, input_path: Path) -> Path:
        """Filtre high-pass pour couper les infra-basses."""
        output = self.cache_dir / "voice_hpf.wav"
        freq = self.config.voice_highpass_freq
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", f"highpass=f={freq}",
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_lowpass(self, input_path: Path) -> Path:
        """Filtre low-pass pour couper les aigus extrêmes."""
        output = self.cache_dir / "voice_lpf.wav"
        freq = self.config.voice_lowpass_freq
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", f"lowpass=f={freq}",
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_presence_boost(self, input_path: Path) -> Path:
        """Boost des fréquences de présence (2-6 kHz) pour la clarté vocale."""
        output = self.cache_dir / "voice_eq.wav"
        boost = self.config.voice_presence_boost
        # Égaliseur paramétrique : boost autour de 3 kHz
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", (
                f"equalizer=f=3000:t=q:w=1:g={boost},"
                f"equalizer=f=5000:t=q:w=1:g={boost * 0.5}"
            ),
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_compression(self, input_path: Path) -> Path:
        """Compression dynamique pour lisser la voix."""
        output = self.cache_dir / "voice_compressed.wav"
        ratio = self.config.voice_compression_ratio
        threshold = self.config.voice_compression_threshold
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", (
                f"acompressor=ratio={ratio}:threshold={threshold}dB:"
                f"attack=10:release=100:makeup=6"
            ),
            str(output),
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _apply_normalization(
        self, input_path: Path, output_path: Path
    ) -> Path:
        """
        Normalisation LUFS selon la norme EBU R128.

        Cible : voice_normalization_target LUFS (typiquement -16 LUFS).
        Assure un volume constant entre toutes les vidéos du pipeline.
        """
        target = self.config.voice_normalization_target
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", (
                f"loudnorm=I={target}:LRA=7:TP=-2.0:"
                f"measured_I=-23:measured_LRA=7:measured_TP=-6:"
                f"measured_thresh=-30:offset=0:linear=true:print_format=summary"
            ),
            str(output_path),
        ]
        await self._run_ffmpeg(cmd)
        return output_path

    @staticmethod
    async def _run_ffmpeg(cmd: list[str]):
        """Exécute une commande FFmpeg et vérifie le succès."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(
                f"FFmpeg failed: {stderr.decode()[:500]}"
            )
```

### 7.2 Musique de fond (Music Pipeline)

#### 7.2.1 Workflow

```
edit_metadata.json
    │
    ▼
┌──────────────────────────────────────────────┐
│ 1. Analyser le mood et le pace du montage    │
│    mood = edit_metadata.mood                 │
│    pace = edit_metadata.pace                 │
│    bpm_estimate = edit_metadata.bpm_estimate │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 2. Mapper mood → Epidemic moods + genres    │
│    Voir tableau 7.2.2                        │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 3. Construire EpidemicSearchQuery            │
│    et appeler MCP                            │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 4. Sélectionner le meilleur résultat         │
│    via select_best_match()                   │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 5. Télécharger le fichier WAV                │
│    → music_raw.wav                           │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 6. Adapter la durée                          │
│    - Tronquer si trop long                   │
│    - Loop si trop court (config.loop)        │
└──────────┬───────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│ 7. Appliquer fades d'entrée/sortie           │
│    → music_background.wav                    │
└──────────────────────────────────────────────┘
```

#### 7.2.2 Table de mapping mood → Epidemic

| Mood (edit_metadata) | BPM estimé | Genres Epidemic | Mots-clés |
|---------------------|-----------|-----------------|-----------|
| `energetic` | 120-140 | electronic, pop, dance | upbeat, energetic, driving, powerful |
| `calm` | 60-90 | ambient, acoustic, classical | calm, peaceful, soft, gentle |
| `professional` | 90-120 | corporate, cinematic | corporate, modern, inspiring, focused |
| `educational` | 80-110 | acoustic, ambient, cinematic | uplifting, focused, warm, gentle |
| `dramatic` | 60-80 | cinematic, orchestral | cinematic, suspenseful, epic |
| `fun` | 120-150 | pop, funk, electronic | fun, playful, quirky, bright |
| `nostalgic` | 80-100 | indie, folk, ambient | nostalgic, sentimental, warm, emotional |
| `intense` | 130-160 | electronic, rock | intense, aggressive, powerful, dark |

#### 7.2.3 Implémentation MusicEngine

```python
class MusicEngine:
    """
    Recherche, téléchargement et adaptation de la musique de fond.

    Utilise le MCP Epidemic Sound pour la recherche.
    Gère le tronçonnage, le looping, et les fades.
    """

    def __init__(self, config: AudioConfig, epidemic_client: EpidemicSoundMCPClient):
        self.config = config
        self.epidemic = epidemic_client
        self.cache_dir = Path(config.cache_dir)

    async def select_and_prepare(
        self,
        edit_meta: EditMetadata,
        output_path: Path,
    ) -> MusicTrack:
        """Cherche, télécharge et prépare la musique de fond."""
        # 1. Déterminer les paramètres de recherche
        moods = self._mood_to_epidemic_moods(edit_meta.mood or "educational")
        genres = self._mood_to_epidemic_genres(edit_meta.mood or "educational")
        bpm = edit_meta.beat_per_minute_estimate

        # 2. Chercher sur Epidemic Sound
        query = self._build_search_query(edit_meta)
        results = await self.epidemic.search_music(
            query=query,
            mood=moods,
            genre=genres,
            bpm_min=bpm - 15 if bpm else None,
            bpm_max=bpm + 15 if bpm else None,
            duration_min=edit_meta.total_duration,
            limit=10,
        )

        # 3. Sélectionner le meilleur
        best = await self.epidemic.select_best_match(
            results,
            target_mood=edit_meta.mood or "educational",
            target_bpm=bpm,
            target_duration=edit_meta.total_duration,
        )

        if best is None:
            raise NoMusicFoundError(
                f"Aucune musique trouvée pour mood={edit_meta.mood}, "
                f"bpm={bpm}, durée={edit_meta.total_duration}s"
            )

        # 4. Télécharger
        music_raw = self.cache_dir / "music_raw.wav"
        await self.epidemic.download_track(best.id, music_raw)

        # 5. Adapter la durée
        track_duration = best.duration
        total_duration = edit_meta.total_duration
        loop_count = 1
        if total_duration > track_duration:
            if self.config.music_loop:
                loop_count = int(total_duration / track_duration) + 1
            # Sinon, on garde tel quel (la musique finira avant la vidéo)

        # 6. Appliquer fades + boucle via FFmpeg
        music_prepared = await self._prepare_track(
            music_raw, output_path, total_duration, loop_count
        )

        return MusicTrack(
            id=f"music_{best.id}",
            title=best.title,
            artist=best.artist or "",
            source="epidemic_sound",
            epidemic_id=best.id,
            local_path=str(music_prepared),
            bpm=best.bpm,
            key=best.key,
            mood=best.moods,
            genres=best.genres,
            duration=best.duration,
            start_time=0.0,
            end_time=total_duration,
            loop_count=loop_count,
            volume_db=self.config.music_volume,
            ducking_applied=False,
            fade_in=self.config.music_fade_in,
            fade_out=self.config.music_fade_out,
            match_score=best.match_score,
            match_reason=f"Meilleur match pour mood={edit_meta.mood}, bpm≈{bpm}",
        )

    async def _prepare_track(
        self,
        input_path: Path,
        output_path: Path,
        total_duration: float,
        loop_count: int,
    ) -> Path:
        """
        Prépare la piste musicale : boucle + fades + tronçonnage.

        Utilise FFmpeg avec le filtre afin pour boucler.
        """
        fade_in = self.config.music_fade_in
        fade_out = self.config.music_fade_out

        if loop_count > 1:
            # Boucle via FFmpeg
            loop_filter = f"aloop=loop={loop_count - 1}:size=20000"
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", str(loop_count - 1),
                "-i", str(input_path),
                "-t", str(total_duration),
                "-af", f"afade=t=in:d={fade_in},afade=t=out:st={total_duration - fade_out}:d={fade_out}",
                str(output_path),
            ]
        else:
            # Simple tronçonnage + fades
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-t", str(total_duration),
                "-af", f"afade=t=in:d={fade_in},afade=t=out:st={total_duration - fade_out}:d={fade_out}",
                str(output_path),
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(f"Music prepare failed: {stderr.decode()[:500]}")

        return output_path

    @staticmethod
    def _mood_to_epidemic_moods(mood: str) -> list[str]:
        """Convertit le mood du montage en moods Epidemic Sound."""
        mapping = {
            "energetic": ["energetic", "upbeat", "powerful", "driving"],
            "calm": ["calm", "peaceful", "ambient", "soft"],
            "professional": ["corporate", "modern", "inspiring", "focused"],
            "educational": ["uplifting", "focused", "warm", "gentle"],
            "dramatic": ["cinematic", "suspenseful", "epic", "intense"],
            "fun": ["fun", "playful", "quirky", "bright"],
            "nostalgic": ["nostalgic", "sentimental", "warm", "emotional"],
            "intense": ["intense", "aggressive", "powerful", "dark"],
        }
        return mapping.get(mood, ["uplifting", "focused", "modern"])

    @staticmethod
    def _mood_to_epidemic_genres(mood: str) -> list[str]:
        mapping = {
            "energetic": ["electronic", "pop", "dance"],
            "calm": ["ambient", "acoustic", "classical"],
            "professional": ["corporate", "cinematic"],
            "educational": ["acoustic", "ambient", "cinematic"],
            "dramatic": ["cinematic", "orchestral"],
            "fun": ["pop", "funk", "electronic"],
            "nostalgic": ["indie", "folk", "ambient"],
            "intense": ["electronic", "rock"],
        }
        return mapping.get(mood, ["ambient", "cinematic", "acoustic"])

    @staticmethod
    def _build_search_query(edit_meta: EditMetadata) -> str:
        """Construit une requête texte à partir du contexte."""
        parts = [edit_meta.mood or "educational"]
        if edit_meta.dominant_colors:
            # Utiliser les couleurs comme indicateur d'ambiance
            pass
        return " ".join(parts)
```

### 7.3 Effets sonores (SFX Engine)

#### 7.3.1 Types d'effets sonores

| Catégorie | Exemples | Durée typique | Usage |
|-----------|---------|---------------|-------|
| **Transition** | whoosh, swoosh, sweep | 0.3-1.5s | Accompagner les transitions entre segments |
| **Accent** | impact, hit, thud, pop | 0.2-1.0s | Souligner un mot important, un moment fort |
| **Atmosphère** | room_tone, ambiance, nature | 5-30s | Fond sonore subtil pour les segments longs |
| **UI** | click, ping, notification | 0.1-0.5s | Apparition de texte, sous-titres karaoke |
| **Text reveal** | typewriter, swoosh | 0.3-1.0s | Texte qui apparaît à l'écran |
| **Cinematic** | riser, impact_big, braam | 1.0-5.0s | Intro, outro, moments dramatiques |
| **Tech** | keyboard, beep, glitch | 0.2-2.0s | Vidéos tech/tutoriels |

#### 7.3.2 Algorithme de suggestion SFX

```
┌──────────────────────────────────────────────┐
│ SFX Suggestion Engine                         │
│                                               │
│ Entrées :                                     │
│   - edit_metadata.scene_changes               │ (timecodes)
│   - edit_metadata.speech_segments             │ (timecodes + text)
│   - transcript.segments                       │ (parole + silences)
│   - config.sfx_concepts                       │ (liste forcée)
│                                               │
│ Règles de suggestion :                        │
│                                               │
│ 1. Transitions :                              │
│    Pour chaque scene_change :                 │
│      → Proposition : whoosh                   │
│         Timing : scene_change - 0.15s         │
│         Durée : ~0.5s                        │
│                                               │
│ 2. Accents sur mots importants :              │
│    Analyser le texte des speech_segments      │
│    → Mots-clés : "important", "attention",    │
│      "clé", "magique", "énorme", "gratuit",   │
│      "nouveau", "secret"                     │
│      → Proposition : impact / pop au moment   │
│         du mot                                │
│                                               │
│ 3. Début de vidéo :                           │
│    → Proposition : riser + impact             │
│       Timing : 0.0s à 2.0s                   │
│                                               │
│ 4. Fin de vidéo :                             │
│    → Proposition : impact + riser out         │
│       Timing : fin - 3.0s à fin               │
│                                               │
│ 5. Silences longs (> 0.8s) :                  │
│    → Proposition : ambiance subtile           │
│       Timing : début silence                  │
│                                               │
│ 6. Apparition de b-roll overlay :             │
│    → Proposition : whoosh court               │
│       Timing : début b-roll                   │
│                                               │
│ 7. Apparition de sous-titres (karaoke) :      │
│    → Proposition : ping subtil                │
│       Timing : chaque nouveau mot             │
│                                               │
│ 8. Config.sfx_concepts forcés :               │
│    → Ajouter sans condition                   │
└──────────────────────────────────────────────┘
```

#### 7.3.3 Implémentation SFXEngine

```python
class SFXEngine:
    """
    Moteur d'effets sonores : suggestion, recherche MCP, placement, mixage.

    Suggère des SFX basés sur les transitions, les moments forts,
    les mots-clés dans le texte, et les concepts forcés de la config.
    """

    def __init__(self, config: AudioConfig, epidemic_client: EpidemicSoundMCPClient):
        self.config = config
        self.epidemic = epidemic_client
        self.cache_dir = Path(config.cache_dir)

    async def suggest_and_place(
        self,
        edit_meta: EditMetadata,
        transcript: TranscriptOutput,
        output_stems_dir: Path,
    ) -> list[SoundEffect]:
        """
        Suggère, cherche, télécharge et place les SFX sur la timeline.

        Retourne une liste de SoundEffect avec chemins locaux résolus.
        """
        suggestions = []

        # 1. Suggestions automatiques
        if self.config.sfx_auto_generate:
            suggestions.extend(self._suggest_transitions(edit_meta))
            suggestions.extend(self._suggest_accent_words(edit_meta))
            suggestions.extend(self._suggest_intro_outro(edit_meta))
            suggestions.extend(self._suggest_silence_ambiance(transcript))
            suggestions.extend(self._suggest_karaoke_pings(edit_meta))

        # 2. Concepts forcés
        for concept in self.config.sfx_concepts:
            suggestions.append(
                SoundEffect(
                    id=f"sfx_forced_{concept}",
                    concept=concept,
                    category="custom",
                    source="epidemic_sound",
                    start_time=0.0,
                    duration=1.0,
                    volume_db=-3.0,
                    auto_generated=False,
                )
            )

        # 3. Limiter le nombre de SFX par minute
        suggestions = self._limit_sfx_per_minute(
            suggestions, edit_meta.total_duration
        )

        # 4. Résoudre les conflits temporels
        suggestions = self._resolve_temporal_conflicts(suggestions)

        # 5. Chercher et télécharger chaque SFX
        resolved = []
        for sfx in suggestions:
            try:
                sfx = await self._resolve_sfx(sfx, output_stems_dir)
                resolved.append(sfx)
            except SFXNotFoundError:
                self._log_warning(f"SFX '{sfx.concept}' non trouvé, ignoré")
                continue

        # 6. Ajuster les volumes selon la config
        for sfx in resolved:
            sfx.volume_db += self.config.sfx_volume

        return resolved

    def _suggest_transitions(self, edit_meta: EditMetadata) -> list[SoundEffect]:
        """Suggère des whoosh pour chaque changement de scène."""
        sfx_list = []
        concepts = ["whoosh", "swoosh", "swipe"]

        for i, change_time in enumerate(edit_meta.scene_changes):
            concept = concepts[i % len(concepts)]
            sfx_list.append(
                SoundEffect(
                    id=f"sfx_trans_{i:04d}",
                    concept=concept,
                    category="transition",
                    source="epidemic_sound",
                    start_time=max(0.0, change_time - 0.15),
                    duration=0.5,
                    volume_db=-2.0,
                    fade_in=0.05,
                    fade_out=0.15,
                    confidence=0.8,
                )
            )

        return sfx_list

    def _suggest_accent_words(self, edit_meta: EditMetadata) -> list[SoundEffect]:
        """
        Suggère des accents sur des mots importants dans le texte.

        Mots-déclencheurs : "important", "attention", "clé", "magique",
        "énorme", "gratuit", "nouveau", "secret", "exactement",
        "critique", "essentiel", "fantastique", "incroyable", "attention"
        """
        trigger_words = [
            "important", "attention", "clé", "magique",
            "énorme", "gratuit", "nouveau", "secret",
            "exactement", "critique", "essentiel",
            "fantastique", "incroyable", "incroyable",
        ]

        sfx_list = []
        for segment in edit_meta.speech_segments:
            text = segment.get("text", "").lower()
            for word in trigger_words:
                if word in text:
                    # Trouver la position approximative du mot
                    words = text.split()
                    try:
                        word_idx = words.index(word)
                        word_ratio = (word_idx + 0.5) / len(words)
                        word_time = segment["start"] + (
                            (segment["end"] - segment["start"]) * word_ratio
                        )
                    except ValueError:
                        continue

                    sfx_list.append(
                        SoundEffect(
                            id=f"sfx_accent_{word}_{segment.get('start', 0):.1f}",
                            concept="impact_pop" if len(word) < 6 else "impact_thud",
                            category="accent",
                            source="epidemic_sound",
                            start_time=word_time,
                            duration=0.4,
                            volume_db=-1.0,
                            fade_in=0.01,
                            fade_out=0.1,
                            confidence=0.7,
                        )
                    )

        return sfx_list

    def _suggest_intro_outro(self, edit_meta: EditMetadata) -> list[SoundEffect]:
        """Suggère un riser pour l'intro et un impact pour l'outro."""
        sfx_list = []
        duration = edit_meta.total_duration

        # Intro riser
        if duration > 3.0:
            sfx_list.append(
                SoundEffect(
                    id="sfx_intro_riser",
                    concept="cinematic_riser",
                    category="cinematic",
                    source="epidemic_sound",
                    start_time=0.0,
                    duration=2.0,
                    volume_db=-4.0,
                    fade_in=0.0,
                    fade_out=0.3,
                    confidence=0.9,
                )
            )

        # Outro impact
        if duration > 5.0:
            sfx_list.append(
                SoundEffect(
                    id="sfx_outro_impact",
                    concept="impact_braam",
                    category="cinematic",
                    source="epidemic_sound",
                    start_time=max(0, duration - 3.0),
                    duration=2.5,
                    volume_db=-3.0,
                    fade_in=0.2,
                    fade_out=0.5,
                    confidence=0.8,
                )
            )

        return sfx_list

    def _suggest_silence_ambiance(
        self, transcript: TranscriptOutput
    ) -> list[SoundEffect]:
        """
        Suggère des ambiances pour les silences longs (> 0.8s).

        Utile pour éviter les trous sonores gênants.
        """
        sfx_list = []
        for seg in transcript.segments:
            if seg.segment_type == "silence":
                silence_duration = seg.end - seg.start
                if silence_duration > 0.8:
                    sfx_list.append(
                        SoundEffect(
                            id=f"sfx_ambiance_{seg.start:.1f}",
                            concept="ambient_room_tone",
                            category="atmosphere",
                            source="epidemic_sound",
                            start_time=seg.start,
                            duration=silence_duration,
                            volume_db=-12.0,  # Très subtil
                            fade_in=0.2,
                            fade_out=0.3,
                            confidence=0.5,
                        )
                    )

        return sfx_list

    def _suggest_karaoke_pings(self, edit_meta: EditMetadata) -> list[SoundEffect]:
        """
        Suggère des pings subtils pour les sous-titres karaoke.

        Très courts et discrets, juste pour donner du rythme.
        """
        # Implémentation simplifiée — ne pas suggérer de ping
        # si le montage a moins de 10 segments
        return []

    def _limit_sfx_per_minute(
        self, suggestions: list[SoundEffect], total_duration: float
    ) -> list[SoundEffect]:
        """
        Limite le nombre de SFX par minute pour éviter la saturation.

        Garde les SFX avec la plus haute confidence.
        """
        if not suggestions:
            return suggestions

        max_per_minute = self.config.sfx_max_per_minute
        minutes = max(1, int(total_duration / 60))
        max_total = minutes * max_per_minute

        if len(suggestions) <= max_total:
            return suggestions

        # Trier par confiance, garder les meilleurs
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions[:max_total]

    def _resolve_temporal_conflicts(
        self, suggestions: list[SoundEffect]
    ) -> list[SoundEffect]:
        """
        Résout les conflits temporels entre SFX :
        - Pas de chevauchement (sauf ambiance)
        - Intervalle minimum configuré
        """
        if len(suggestions) <= 1:
            return suggestions

        # Séparer les ambiances (peuvent se chevaucher)
        ambiances = [s for s in suggestions if s.category == "atmosphere"]
        others = [
            s for s in suggestions if s.category != "atmosphere"
        ]

        # Trier par start_time
        others.sort(key=lambda s: s.start_time)

        # Résoudre les conflits
        resolved = []
        last_end = -self.config.sfx_min_interval

        for sfx in others:
            if sfx.start_time >= last_end + self.config.sfx_min_interval:
                resolved.append(sfx)
                last_end = sfx.end_time
            elif sfx.confidence > (resolved[-1].confidence if resolved else 0):
                # Remplacer le dernier par celui-ci
                if resolved:
                    resolved.pop()
                resolved.append(sfx)
                last_end = sfx.end_time
            # Sinon, ignorer le SFX en conflit

        return resolved + ambiances

    async def _resolve_sfx(
        self, sfx: SoundEffect, output_dir: Path
    ) -> SoundEffect:
        """
        Cherche le SFX sur Epidemic Sound, le télécharge, et le prépare.

        Si non trouvé, génère un son placeholder.
        """
        # Chercher le SFX
        duration_min = max(0.1, sfx.duration - 0.2)
        duration_max = sfx.duration + 2.0

        results = await self.epidemic.search_sfx(
            concept=sfx.concept,
            duration_min=duration_min,
            duration_max=duration_max,
            limit=5,
        )

        if not results:
            # Fallback : générer un son simple
            return await self._generate_placeholder_sfx(sfx, output_dir)

        best = results[0]

        # Télécharger
        local_path = output_dir / f"sfx_{sfx.id}.wav"
        await self.epidemic.download_track(best.id, local_path)

        sfx.source = "epidemic_sound"
        sfx.epidemic_id = best.id
        sfx.local_path = str(local_path)
        sfx.duration = min(sfx.duration, best.duration)

        # Tronquer à la durée exacte
        sfx.local_path = str(
            await self._trim_sfx(Path(local_path), sfx)
        )

        return sfx

    async def _trim_sfx(self, input_path: Path, sfx: SoundEffect) -> Path:
        """Tronque et applique les fades sur un SFX."""
        output = input_path.parent / f"{input_path.stem}_trimmed.wav"
        fade_in = sfx.fade_in
        fade_out = sfx.fade_out
        duration = sfx.duration

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-t", str(duration),
            "-af", (
                f"afade=t=in:d={fade_in},"
                f"afade=t=out:st={duration - fade_out}:d={fade_out}"
            ),
            str(output),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(f"SFX trim failed: {stderr.decode()[:500]}")

        return output

    async def _generate_placeholder_sfx(
        self, sfx: SoundEffect, output_dir: Path
    ) -> SoundEffect:
        """Génère un son placeholder via FFmpeg (sine wave + noise)."""
        output = output_dir / f"sfx_{sfx.id}_placeholder.wav"
        duration = sfx.duration

        # Générer un 'pop' simple : sine wave 440Hz avec enveloppe
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", (
                f"sine=frequency=440:duration={duration},"
                f"volume=0.3,afade=t=in:d=0.01,afade=t=out:st={duration - 0.1}:d=0.1"
            ),
            str(output),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        sfx.local_path = str(output)
        sfx.source = "generated"
        return sfx
```

---

## 8. Ducking intelligent

### 8.1 Principe

Le ducking (ou "sidechain compression") est la réduction automatique du volume de la musique de fond pendant que la personne parle, avec un retour progressif du volume pendant les silences et pauses.

```
Volume
  ▲
  │    ┌────────┐              ┌──────┐
  │    │        │    Musique   │      │
  │────┤  Voix  ├──────────────┤ Voix ├───
  │    │        │    duckée    │      │
  │    └───┬────┘              └──┬───┘
  │        ▼                      ▼
  │    ┌─────────────────────────────────────┐
  │    │         Musique réduite             │
  │    │         de ducking_level dB         │
  │    └─────────────────────────────────────┘
  └──────────────────────────────────────────────► Temps
       Parole    Silence       Parole
```

### 8.2 Deux approches de ducking

#### Approche A : Sidechain compression FFmpeg (temps réel, recommandée)

Utilise le filtre `sidechaincompress` de FFmpeg qui écoute la piste vocale et compresse la musique en temps réel.

```python
class DuckingEngine:
    """
    Moteur de ducking automatique.

    Deux modes :
    - ffmpeg_sidechain : utilise sidechaincompress (recommandé, temps réel)
    - frame_by_frame : courbe d'automation calculée (plus de contrôle, plus lent)
    """

    MODE_FFMPEG_SIDECHAIN = "ffmpeg_sidechain"
    MODE_FRAME_BY_FRAME = "frame_by_frame"

    def __init__(self, config: AudioConfig):
        self.config = config
        self.cache_dir = Path(config.cache_dir)

    async def apply_ffmpeg_sidechain(
        self,
        music_path: Path,
        voice_path: Path,
        speech_segments: list[dict],
        output_path: Path,
    ) -> Path:
        """
        Applique le ducking via sidechaincompress FFmpeg.

        Avantages :
        - Temps réel, pas de pré-calcul
        - Réagit aux vrais niveaux audio de la voix
        - Attack/release paramétrables

        Inconvénients :
        - Moins de contrôle sur la courbe exacte
        - Peut réagir à des bruits parasites
        """
        level = self.config.ducking_level  # dB de réduction
        attack = self.config.ducking_attack
        release = self.config.ducking_release
        threshold = self.config.ducking_threshold

        cmd = [
            "ffmpeg", "-y",
            "-i", str(music_path),            # Input 0 : musique
            "-i", str(voice_path),            # Input 1 : voix (sidechain)
            "-filter_complex", (
                f"[0:a]volume=1.0[music];"
                f"[1:a]asplit=2[voice][side];"
                f"[music][side]sidechaincompress="
                f"threshold={threshold}dB:"
                f"ratio=1/{(abs(level) / 6):.1f}:"  # Ratio basé sur ducking_level
                f"attack={attack}:"
                f"release={release}:"
                f"makeup=0"
                f"[ducked];"
                f"[ducked][voice]amix=inputs=2:duration=first:dropout_transition=2[out]"
            ),
            "-map", "[out]",
            "-ac", "2",
            "-ar", str(self.config.export_sample_rate),
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(f"Sidechain ducking failed: {stderr.decode()[:500]}")

        return output_path

    async def apply_frame_by_frame(
        self,
        music_path: Path,
        voice_path: Path,
        speech_segments: list[dict],
        output_path: Path,
    ) -> Path:
        """
        Applique le ducking via courbe d'automation calculée frame par frame.

        Avantages :
        - Contrôle total sur la courbe
        - Peut anticiper les prises de parole (pre-roll)
        - Ignore les bruits parasites hors parole

        Inconvénients :
        - Plus lent (doit analyser tout l'audio)
        - Pré-calcul nécessaire

        Algorithme :
        1. Pour chaque speech_segment :
           - attack_time avant le début : début de réduction
           - release_time après la fin : retour progressif
        2. Construire une courbe gain(dB) = f(temps)
        3. Appliquer la courbe via le filtre volume=expr de FFmpeg
        """
        # 1. Construire la courbe de ducking
        curve = self._build_ducking_curve(speech_segments)

        # 2. Générer l'expression FFmpeg pour le volume
        expr = self._curve_to_ffmpeg_expr(curve)

        # 3. Appliquer via FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(music_path),
            "-af", f"volume='{expr}'",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(f"Frame-by-frame ducking failed: {stderr.decode()[:500]}")

        return output_path

    def _build_ducking_curve(
        self, speech_segments: list[dict]
    ) -> list[DuckingFrame]:
        """
        Construit la courbe de ducking à partir des segments de parole.

        Chaque segment de parole génère :
        - attack : réduction progressive (ducking_attack secondes)
        - sustain : maintien de la réduction (ducking_level dB)
        - release : retour progressif (ducking_release secondes)

        Entre les segments : volume normal (0 dB)
        """
        if not speech_segments:
            return []

        curve = []
        attack = self.config.ducking_attack
        release = self.config.ducking_release
        level = self.config.ducking_level  # Négatif

        # Trier par start
        segments = sorted(speech_segments, key=lambda s: s["start"])

        # Ajouter un point à t=0
        curve.append(DuckingFrame(time=0.0, gain_db=0.0))

        for seg in segments:
            start = seg["start"]
            end = seg["end"]

            # Pre-roll : début de l'attaque avant la parole
            pre_roll = max(0.0, start - attack)

            # Phase d'attaque
            curve.append(DuckingFrame(time=pre_roll, gain_db=0.0))
            curve.append(DuckingFrame(time=start, gain_db=level))

            # Pendant la parole : maintien
            curve.append(DuckingFrame(time=end, gain_db=level))

            # Phase de release
            post_roll = end + release
            curve.append(DuckingFrame(time=post_roll, gain_db=0.0))

        return curve

    def _curve_to_ffmpeg_expr(
        self, curve: list[DuckingFrame]
    ) -> str:
        """
        Convertit la courbe de ducking en expression FFmpeg.

        Utilise une série de 'if' imbriqués basés sur le timecode.
        Format : "if(lt(t,5),1,if(lt(t,5.1),0.5,...))"

        Le résultat est un multiplicateur linéaire (1.0 = pas de changement).
        """
        if not curve:
            return "1"

        # Trier les points par temps
        sorted_pts = sorted(curve, key=lambda p: p.time)
        if len(sorted_pts) < 2:
            return "1"

        # Construire l'expression : série de if imbriqués
        # Convertir dB en facteur linéaire : 10^(dB/20)
        def db_to_linear(db: float) -> float:
            return 10 ** (db / 20)

        # On génère des paliers avec interpolation linéaire entre les points
        # Pour simplifier, on utilise l'approche par paliers avec crossfade
        expr_parts = []

        for i in range(len(sorted_pts) - 1):
            t1 = sorted_pts[i].time
            t2 = sorted_pts[i + 1].time
            g1 = db_to_linear(sorted_pts[i].gain_db)
            g2 = db_to_linear(sorted_pts[i + 1].gain_db)

            # Interpolation linéaire entre t1 et t2
            # gain(t) = g1 + (g2-g1) * ((t-t1)/(t2-t1))
            if abs(g2 - g1) < 0.001:
                # Paller constant
                expr_parts.append(
                    f"if(lt(t,{t2}),{g1:.4f},"
                )
            else:
                # Rampe linéaire
                slope = (g2 - g1) / (t2 - t1)
                expr_parts.append(
                    f"if(lt(t,{t2}),{g1:.4f}+{slope:.6f}*(t-{t1}),"
                )

        # Dernier point : valeur constante
        expr_parts.append(f"{db_to_linear(sorted_pts[-1].gain_db):.4f}")

        # Fermer tous les if
        expr_parts.append(")" * len(expr_parts))

        return "".join(expr_parts)
```

#### Approche B : Frame-by-frame (précision optimale)

L'approche frame-by-frame offre un contrôle plus précis car elle peut **anticiper** la parole (pre-roll) et ajuster la courbe avec des rampes douces plutôt que des paliers brusques. Elle est recommandée pour les vidéos où la qualité audio est critique.

### 8.3 Configuration fine du ducking

| Paramètre | Valeur par défaut | Description | Effet |
|-----------|------------------|-------------|-------|
| `ducking_level` | -12 dB | Réduction du volume musique | Plus négatif = musique plus basse |
| `ducking_attack` | 0.05 s | Temps pour atteindre la réduction | Trop court = coupure brusque |
| `ducking_release` | 0.30 s | Temps pour revenir au volume normal | Trop long = musique qui tarde à revenir |
| `ducking_threshold` | -20 dBFS | Seuil de déclenchement | Trop bas = ducking qui ne se déclenche pas |

**Recommandations :**

| Type de contenu | ducking_level | ducking_attack | ducking_release | ducking_threshold |
|----------------|--------------|----------------|-----------------|-------------------|
| Tutoriel lent | -8 dB | 0.10 s | 0.50 s | -25 dBFS |
| Tutoriel normal | -12 dB | 0.05 s | 0.30 s | -20 dBFS |
| Vlog énergique | -15 dB | 0.03 s | 0.20 s | -18 dBFS |
| Podcast | -10 dB | 0.08 s | 0.40 s | -22 dBFS |
| Gaming | -18 dB | 0.02 s | 0.15 s | -16 dBFS |

### 8.4 Détection des silences pour le ducking

Le ducking utilise les `speech_segments` fournis par l'Agent #3 dans `edit_metadata.json`. Si ces données ne sont pas disponibles, le transcript de l'Agent #1 est utilisé pour déterminer les segments de parole.

```python
class DuckingSpeechDetector:
    """
    Détecte les segments de parole pour le ducking.

    Sources (par ordre de préférence) :
    1. edit_metadata.speech_segments  (direct depuis Agent #3)
    2. transcript.segments            (fallback Agent #1)
    3. Analyse audio directe          (ultime fallback via librosa)
    """

    @staticmethod
    def extract_speech_segments(
        edit_meta: Optional[EditMetadata],
        transcript: Optional[TranscriptOutput],
        audio_path: Optional[Path] = None,
    ) -> list[SpeechSegmentForDucking]:
        """Extrait les segments de parole pour le ducking."""

        # 1. Edit metadata (meilleure source)
        if edit_meta and edit_meta.speech_segments:
            return [
                SpeechSegmentForDucking(
                    start=s["start"],
                    end=s["end"],
                    text=s.get("text", ""),
                )
                for s in edit_meta.speech_segments
            ]

        # 2. Transcript (fallback principal)
        if transcript:
            return [
                SpeechSegmentForDucking(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
                for seg in transcript.segments
                if seg.segment_type == "speech"
            ]

        # 3. Analyse audio (ultime fallback)
        if audio_path:
            return DuckingSpeechDetector._detect_from_audio(audio_path)

        return []

    @staticmethod
    def _detect_from_audio(audio_path: Path) -> list[SpeechSegmentForDucking]:
        """Détecte les segments de parole par analyse RMS."""
        import librosa
        import numpy as np

        y, sr = librosa.load(str(audio_path), sr=16000, mono=True)

        # Calculer l'énergie RMS par frame (50ms)
        frame_length = int(0.05 * sr)
        hop_length = int(0.025 * sr)
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        # Seuil adaptatif : 30% du RMS median
        threshold = np.median(rms[rms > 0]) * 0.3

        # Détection des régions actives
        is_speech = rms > threshold

        # Conversion en segments
        segments = []
        in_speech = False
        start = 0.0

        for i, speaking in enumerate(is_speech):
            time = i * hop_length / sr
            if speaking and not in_speech:
                start = time
                in_speech = True
            elif not speaking and in_speech:
                end = time
                if end - start > 0.1:  # Ignorer les micro-silences
                    segments.append(
                        SpeechSegmentForDucking(start=start, end=end)
                    )
                in_speech = False

        # Dernier segment
        if in_speech:
            end = len(is_speech) * hop_length / sr
            segments.append(
                SpeechSegmentForDucking(start=start, end=end)
            )

        return segments
```

---

## 9. Sync guard

### 9.1 Problématique

La désynchronisation audio/vidéo est un problème majeur dans les pipelines audio. Elle peut survenir à plusieurs étapes :

| Étape | Risque de désync | Cause |
|-------|-----------------|-------|
| Extraction audio depuis la vidéo | Faible | FFmpeg extrait correctement |
| Traitement vocal (filtres, EQ, etc.) | Faible | Filtres conservent la durée |
| Ducking sidechain | **Élevé** | `sidechaincompress` peut altérer la durée |
| Mixage des pistes | **Moyen** | `amix` peut décaler si durées inégales |
| Mux audio dans la vidéo | **Moyen** | Mauvaise synchronisation des streams |

### 9.2 Implémentation SyncGuard

```python
class SyncGuard:
    """
    Vérifie et corrige la synchronisation audio/vidéo après chaque étape critique.

    Tolérance : config.sync_tolerance_ms (défaut 40 ms)
    Au-delà : correction automatique ou erreur selon config.sync_auto_correct
    """

    THRESHOLD_MS = 40  # Sera écrasé par config

    def __init__(self, config: AudioConfig):
        self.config = config
        self.THRESHOLD_MS = config.sync_tolerance_ms

    async def verify(
        self, video_path: Path, audio_path: Path
    ) -> SyncReport:
        """
        Vérifie la synchronisation entre une vidéo et un fichier audio.

        Compare les durées totales et les premiers timestamps PTS.

        Retourne un SyncReport avec offset_ms.
        """
        # Analyser la vidéo
        video_probe = await self._probe(video_path)
        audio_probe = await self._probe(audio_path)

        # Comparer les durées
        video_duration = float(
            next(
                (s.get("duration", 0) for s in video_probe.get("streams", [])
                 if s["codec_type"] == "video"),
                0,
            )
        )
        audio_duration = float(
            next(
                (s.get("duration", 0) for s in audio_probe.get("streams", [])
                 if s["codec_type"] == "audio"),
                audio_probe.get("format", {}).get("duration", 0),
            )
        ) if audio_probe.get("streams") else float(
            audio_probe.get("format", {}).get("duration", 0)
        )

        # Décalage de durée
        duration_diff_ms = abs(video_duration - audio_duration) * 1000

        # Vérifier les PTS si on a une vidéo avec audio
        video_audio_stream = next(
            (s for s in video_probe.get("streams", [])
             if s["codec_type"] == "audio"), None
        )
        video_video_stream = next(
            (s for s in video_probe.get("streams", [])
             if s["codec_type"] == "video"), None
        )

        pts_offset_ms = 0.0
        if video_audio_stream and video_video_stream:
            audio_pts = video_audio_stream.get("start_pts", 0)
            video_pts = video_video_stream.get("start_pts", 0)
            time_base = self._parse_time_base(
                video_audio_stream.get("time_base", "1/1000")
            )
            pts_offset_ms = abs(audio_pts - video_pts) * time_base * 1000

        # L'offset principal est le max des deux mesures
        offset_ms = max(duration_diff_ms, pts_offset_ms)
        synced = offset_ms <= self.THRESHOLD_MS

        return SyncReport(
            synced=synced,
            offset_ms=offset_ms,
            video_duration_sec=video_duration,
            audio_duration_sec=audio_duration,
            duration_diff_ms=duration_diff_ms,
            pts_offset_ms=pts_offset_ms,
            tolerance_ms=self.THRESHOLD_MS,
        )

    async def verify_muxed_video(self, video_path: Path) -> SyncReport:
        """
        Vérifie la synchronisation dans une vidéo déjà muxée.

        Utilise FFprobe pour comparer les streams audio et vidéo.
        """
        probe = await self._probe(video_path)

        audio_stream = next(
            (s for s in probe.get("streams", [])
             if s["codec_type"] == "audio"), None
        )
        video_stream = next(
            (s for s in probe.get("streams", [])
             if s["codec_type"] == "video"), None
        )

        if not audio_stream or not video_stream:
            return SyncReport(
                synced=True,
                offset_ms=0.0,
                error="Impossible de trouver les streams audio/vidéo",
            )

        # Comparer les durées
        video_dur = float(video_stream.get("duration", 0))
        audio_dur = float(audio_stream.get("duration", 0))
        duration_diff_ms = abs(video_dur - audio_dur) * 1000

        # Comparer les start_pts
        audio_pts = audio_stream.get("start_pts", 0)
        video_pts = video_stream.get("start_pts", 0)
        time_base = self._parse_time_base(
            audio_stream.get("time_base", "1/1000")
        )
        pts_offset_ms = abs(audio_pts - video_pts) * time_base * 1000

        offset_ms = max(duration_diff_ms, pts_offset_ms)
        synced = offset_ms <= self.THRESHOLD_MS

        return SyncReport(
            synced=synced,
            offset_ms=offset_ms,
            video_duration_sec=video_dur,
            audio_duration_sec=audio_dur,
            duration_diff_ms=duration_diff_ms,
            pts_offset_ms=pts_offset_ms,
            video_stream_index=video_stream.get("index"),
            audio_stream_index=audio_stream.get("index"),
            tolerance_ms=self.THRESHOLD_MS,
        )

    async def auto_correct(
        self, video_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """
        Corrige automatiquement la désynchronisation.

        Stratégie :
        - Si audio plus court : ajouter du silence à la fin
        - Si audio plus long : tronquer
        - Si PTS décalé : utiliser -itsoffset pour décaler
        """
        report = await self.verify(video_path, audio_path)

        if report.synced:
            # Déjà synchrone, simple mux
            return await self._mux_simple(video_path, audio_path, output_path)

        video_dur = report.video_duration_sec
        audio_dur = report.audio_duration_sec

        if abs(audio_dur - video_dur) * 1000 > self.THRESHOLD_MS:
            # Corriger la durée
            if audio_dur < video_dur:
                # Ajouter du silence
                silence_dur = video_dur - audio_dur
                corrected_audio = audio_path.parent / f"{audio_path.stem}_sync_corrected.wav"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(audio_path),
                    "-af", f"apad=pad_dur={silence_dur}",
                    str(corrected_audio),
                ]
                await self._run_ffmpeg(cmd)
                audio_path = corrected_audio
            else:
                # Tronquer
                corrected_audio = audio_path.parent / f"{audio_path.stem}_sync_corrected.wav"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(audio_path),
                    "-t", str(video_dur),
                    str(corrected_audio),
                ]
                await self._run_ffmpeg(cmd)
                audio_path = corrected_audio

        # Mux final
        return await self._mux_simple(video_path, audio_path, output_path)

    async def _mux_simple(
        self, video_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """Remplace la piste audio de la vidéo par le fichier audio fourni."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",           # Garder la vidéo originale
            "-c:a", self.config.export_codec,
            "-b:a", self.config.export_bitrate,
            "-map", "0:v:0",          # Vidéo du premier input
            "-map", "1:a:0",          # Audio du second input
            "-shortest",              # Durée = plus court des deux
            "-movflags", "+faststart",
            str(output_path),
        ]
        await self._run_ffmpeg(cmd)
        return output_path

    @staticmethod
    async def _probe(path: Path) -> dict:
        """Probe un fichier avec FFprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return json.loads(stdout)

    @staticmethod
    def _parse_time_base(tb: str) -> float:
        try:
            num, den = tb.split("/")
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 1.0 / 1000.0

    @staticmethod
    async def _run_ffmpeg(cmd: list[str]):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegAudioError(f"FFmpeg failed: {stderr.decode()[:500]}")


class SyncReport(BaseModel):
    """Rapport de synchronisation."""
    synced: bool
    offset_ms: float
    video_duration_sec: float = 0.0
    audio_duration_sec: float = 0.0
    duration_diff_ms: float = 0.0
    pts_offset_ms: float = 0.0
    video_stream_index: Optional[int] = None
    audio_stream_index: Optional[int] = None
    tolerance_ms: float = 40.0
    error: Optional[str] = None
```

### 9.3 Points de vérification obligatoires

Le SyncGuard doit être appelé après chaque étape critique :

```python
class SyncCheckpoints:
    """Points de vérification obligatoires dans le pipeline."""

    # Étape 1 : Après extraction audio de la vidéo
    CHECKPOINT_EXTRACT = "after_extract"

    # Étape 2 : Après traitement vocal
    CHECKPOINT_VOICE = "after_voice_pipeline"

    # Étape 3 : Après ducking
    CHECKPOINT_DUCKING = "after_ducking"

    # Étape 4 : Après mix master
    CHECKPOINT_MASTER = "after_master_mix"

    # Étape 5 : APRÈS MUX (obligatoire) — point de contrôle final
    CHECKPOINT_FINAL = "after_mux_final"
```

**Règle d'or** : Le checkpoint final **doit** passer (offset < tolerance_ms) avant de livrer la vidéo à l'Agent #5. Si le check échoue et que `sync_auto_correct` est désactivé, le pipeline doit lever une `AudioSyncError` et ne pas livrer de vidéo désynchronisée.

---

## 10. Boucle Qualité (Agent #5)

### 10.1 Réception des feedbacks

L'Agent #5 (Gemini) analyse la vidéo finale et peut renvoyer des feedbacks spécifiques à l'audio :

```python
class AudioQualityFeedback(BaseModel):
    """Feedback de l'Agent #5 spécifique à l'audio."""
    iteration: int
    overall_score: float = Field(ge=0, le=10)

    # Métriques audio
    loudness_ok: bool = True
    voice_clearness: float = Field(ge=0, le=1)
    music_level_balance: float = Field(ge=0, le=1)
    ducking_quality: float = Field(ge=0, le=1)
    sfx_relevance: float = Field(ge=0, le=1)
    sync_ok: bool = True

    # Problèmes détectés
    issues: list[AudioIssue] = []
    suggestions: list[str] = []


class AudioIssue(BaseModel):
    severity: Literal["critical", "major", "minor", "suggestion"]
    category: Literal[
        "ducking", "volume", "sync", "loudness",
        "noise", "eq", "sfx_placement", "music_mood"
    ]
    description: str
    suggested_action: Optional[str] = None
```

### 10.2 Corrections automatiques possibles

| Problème | Correction | Paramètre |
|----------|-----------|-----------|
| Musique trop forte | Baisser `music_volume` | -2 dB |
| Ducking insuffisant | Augmenter `ducking_level` | -3 dB supplémentaires |
| Ducking trop lent | Réduire `ducking_release` | 0.20 s |
| Voix peu claire | Augmenter `voice_presence_boost` | +1 dB |
| Trop de SFX | Réduire `sfx_max_per_minute` | 4 |
| Désync détectée | Forcer `sync_auto_correct` | true |
| Bruit de fond | Activer `voice_noise_reduction` | true |

---

## 11. Interface CLI

### 11.1 Commandes

```bash
# Usage principal : pipeline audio complet
video-automation agent audio \
    --input montage_rendu.mp4 \
    --edit-metadata edit_metadata.json \
    --transcript transcript.json \
    --config config.yaml \
    --output /output/montage_audio.mp4

# Mode preview (rapide, sans stems)
video-automation agent audio \
    --input montage_rendu.mp4 \
    --edit-metadata edit_metadata.json \
    --transcript transcript.json \
    --preview \
    --output /output/montage_audio_preview.mp4

# Mode voice only (pas de musique ni SFX)
video-automation agent audio \
    --input montage_rendu.mp4 \
    --edit-metadata edit_metadata.json \
    --voice-only \
    --output /output/montage_audio_voice.mp4

# Planification uniquement (dry run)
video-automation agent audio \
    --input montage_rendu.mp4 \
    --edit-metadata edit_metadata.json \
    --transcript transcript.json \
    --dry-run \
    --output /output/audio_plan.json

# Recherche de musique seulement
video-automation agent audio search-music \
    --mood "energetic" \
    --bpm 120 \
    --duration 60 \
    --limit 5

# Recherche d'SFX seulement
video-automation agent audio search-sfx \
    --concept "whoosh" \
    --duration 0.5

# Vérification de synchronisation
video-automation agent audio verify-sync \
    --video montage_audio.mp4

# Re-mux (remplace l'audio sans retraiter)
video-automation agent audio remux \
    --video montage_rendu.mp4 \
    --audio master_mix.wav \
    --output /output/montage_audio.mp4

# Export des stems seulement (à partir d'un mix existant)
video-automation agent audio export-stems \
    --input montage_audio.mp4 \
    --output-dir /output/stems/
```

### 11.2 Implémentation CLI (Typer)

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="Agent #4 — Design Audio")

@app.command()
def audio(
    input: Path = typer.Option(..., "--input", "-i",
                                help="montage_rendu.mp4 from Agent #3"),
    edit_metadata: Path = typer.Option(..., "--edit-metadata", "-e",
                                        help="edit_metadata.json from Agent #3"),
    transcript: Optional[Path] = typer.Option(None, "--transcript", "-t",
                                                help="transcript.json from Agent #1"),
    config: Path = typer.Option("config.yaml", "--config", "-c",
                                 help="Audio configuration file"),
    output: Path = typer.Option("montage_audio.mp4", "--output", "-o",
                                 help="Output video path"),
    preview: bool = typer.Option(False, "--preview", "-p",
                                  help="Generate quick preview (no stems)"),
    voice_only: bool = typer.Option(False, "--voice-only",
                                     help="Skip music and SFX"),
    dry_run: bool = typer.Option(False, "--dry-run",
                                  help="Only generate audio plan (no render)"),
    stems_dir: Optional[Path] = typer.Option(None, "--stems-dir",
                                               help="Override stems output directory"),
):
    """Execute le pipeline de design audio complet."""
    asyncio.run(_run_audio(
        input, edit_metadata, transcript, config, output,
        preview, voice_only, dry_run, stems_dir,
    ))


@app.command()
def search_music(
    mood: str = typer.Option("educational", "--mood", "-m"),
    bpm: Optional[int] = typer.Option(None, "--bpm"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d"),
    limit: int = typer.Option(5, "--limit", "-l"),
    output: Optional[Path] = typer.Option(None, "--output", "-o",
                                            help="Save results as JSON"),
):
    """Recherche de musique via Epidemic Sound MCP."""
    asyncio.run(_run_search_music(mood, bpm, duration, limit, output))


@app.command()
def search_sfx(
    concept: str = typer.Argument(..., help="Concept SFX"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d"),
    limit: int = typer.Option(5, "--limit", "-l"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Recherche d'effets sonores via Epidemic Sound MCP."""
    asyncio.run(_run_search_sfx(concept, duration, limit, output))


@app.command()
def verify_sync(
    video: Path = typer.Argument(..., help="Video file to check"),
    tolerance: float = typer.Option(40.0, "--tolerance", "-t",
                                     help="Tolerance in ms"),
):
    """Vérifie la synchronisation audio/vidéo d'un fichier."""
    asyncio.run(_run_verify_sync(video, tolerance))


@app.command()
def remux(
    video: Path = typer.Option(..., "--video", "-v"),
    audio: Path = typer.Option(..., "--audio", "-a"),
    output: Path = typer.Option("remuxed.mp4", "--output", "-o"),
):
    """Remplace l'audio d'une vidéo par un fichier audio externe."""
    asyncio.run(_run_remux(video, audio, output))


@app.command()
def export_stems(
    input: Path = typer.Option(..., "--input", "-i"),
    output_dir: Path = typer.Option("stems", "--output-dir", "-o"),
):
    """Extrait les pistes audio séparées d'une vidéo."""
    asyncio.run(_run_export_stems(input, output_dir))


@app.command()
def list_moods():
    """Liste les moods disponibles pour la recherche."""
    moods = [
        "energetic", "calm", "professional", "educational",
        "dramatic", "fun", "nostalgic", "intense",
        "uplifting", "focused", "cinematic", "peaceful",
    ]
    typer.echo("Moods disponibles pour la recherche musicale :")
    for m in moods:
        typer.echo(f"  • {m}")


if __name__ == "__main__":
    app()
```

### 11.3 Compatibilité docker-compose

La CLI s'intègre dans l'architecture docker-compose existante :

```yaml
# docker-compose.yml (extrait)
services:
  agent-4-audio:
    build: ./agents/agent-4-audio
    volumes:
      - /data/renders:/data/renders          # Montage Agent #3
      - /data/audio:/data/audio              # Sortie audio
      - /data/transcriptions:/data/transcriptions  # Transcript Agent #1
      - /data/cutlists:/data/cutlists        # Edit metadata Agent #3
      - ./config:/app/config                 # Config
    env_file:
      - .env                                 # Clé API Epidemic Sound
    command: >
      python -m agent4_audio.cli audio
        --input /data/renders/montage_rendu.mp4
        --edit-metadata /data/cutlists/edit_metadata.json
        --transcript /data/transcriptions/transcript.json
        --config /app/config/config.yaml
        --output /data/audio/montage_audio.mp4
```

---

## 12. Mode Preview

### 12.1 Objectif

Générer une version **rapide** de l'audio pour itération rapide sans attendre le pipeline complet.

### 12.2 Optimisations

```python
class PreviewMode:
    """
    Optimisations pour le mode preview :

    1. Pas d'export de stems (gain de temps disque)
    2. Ducking simplifié (courbe pré-calculée, pas de sidechain)
    3. SFX limités (max 3 effets, pas de recherche MCP)
    4. Pas de normalisation LUFS (volume direct)
    5. Compression légère uniquement
    6. Musique non téléchargée si déjà en cache
    7. Mono output (pas de stéréo)
    8. Bitrate réduit

    Timing estimé : 30-60s pour une vidéo de 10min (vs 5-10min en full)
    """
```

### 12.3 Cache

```python
class AudioCache:
    """Cache les fichiers audio intermédiaires."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached(self, key: str, config_hash: str) -> Path | None:
        """Vérifie si un fichier audio est en cache."""
        cached = self.cache_dir / f"{key}_{config_hash}.wav"
        return cached if cached.exists() else None

    def save(self, key: str, config_hash: str, path: Path) -> Path:
        """Sauvegarde un fichier dans le cache."""
        dest = self.cache_dir / f"{key}_{config_hash}.wav"
        shutil.copy2(path, dest)
        return dest

    def invalidate(self, key: str | None = None):
        """Invalide le cache."""
        if key:
            for f in self.cache_dir.glob(f"{key}_*.wav"):
                f.unlink()
        else:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir()
```

---

## 13. Structure du module

```
src/agent4_audio/
├── __init__.py                      # Exports publics, version
├── cli.py                           # Interface CLI (Typer)
├── config.py                        # AudioConfig Pydantic
├── models.py                        # Tous les modèles Pydantic (SoundEffect, MusicTrack, etc.)
├── orchestrator.py                  # Orchestrateur principal (AudioPipeline)
│
├── voice_pipeline.py               # VoicePipeline (extraction, gate, denoise, EQ, compression, normalize)
├── music_engine.py                  # MusicEngine (recherche MCP, téléchargement, adaptation)
├── sfx_engine.py                    # SFXEngine (suggestion, placement, téléchargement)
│
├── ducking_engine.py                # DuckingEngine (sidechain FFmpeg + frame-by-frame)
├── ducking_detector.py             # DuckingSpeechDetector (extraction segments parole)
│
├── sync_guard.py                    # SyncGuard (vérification + correction automatique)
│
├── epidemic_client.py               # EpidemicSoundMCPClient (client MCP)
├── custom_exceptions.py            # AudioError, FFmpegAudioError, etc.
│
├── mix_engine.py                    # MixEngine (master mix, limiter, stems export)
├── preview.py                       # PreviewMode
├── cache.py                         # AudioCache
│
└── tests/
    ├── __init__.py
    ├── test_voice_pipeline.py       # Tests extraction, compression, normalization
    ├── test_music_engine.py         # Tests recherche, selection, adaptation
    ├── test_sfx_engine.py           # Tests suggestion, placement, conflits
    ├── test_ducking.py              # Tests courbe ducking, sidechain, frame-by-frame
    ├── test_sync_guard.py           # Tests vérification sync, correction
    ├── test_epidemic_client.py      # Tests MCP (mockés)
    ├── test_mix_engine.py           # Tests mix, stems export
    ├── test_integration.py          # Tests pipeline complet
    └── fixtures/
        ├── test_video_10s.mp4       # Vidéo de test 10 secondes
        ├── test_voice.wav           # Échantillon vocal
        ├── test_music.wav           # Échantillon musical
        ├── test_sfx.wav             # Échantillon SFX
        ├── sample_edit_metadata.json
        └── sample_transcript.json
```

---

## 14. Pièges connus & mitigations

### 14.1 Epidemic Sound MCP indisponible

| Problème | Impact | Mitigation |
|----------|--------|------------|
| API Epidemic Sound down | Pas de musique ni SFX | Mode dégradé : voix seule + cache local |
| Clé API invalide | 401 Unauthorized | Logger l'erreur, fallback voice-only |
| Rate limiting | Réponses 429 | Exponential backoff, cache des résultats |
| Latence API | Pipeline lent | Timeout configurable, cache des téléchargements |
| Changement API MCP | Break compatibilité | Versionner le client, tests d'intégration |

### 14.2 Qualité audio

| Problème | Cause | Mitigation |
|----------|-------|------------|
| Voix métallique | Trop de compression | Réduire `voice_compression_ratio` à 2:1 |
| Souffle audible | Noise reduction trop faible | Augmenter `voice_noise_reduction_strength` à 0.5 |
| Musique qui "pompe" | Ducking mal réglé | Augmenter `ducking_release` à 0.5 s |
| SFX trop forts | Volume mal calibré | Baisser `sfx_volume` |
| Écrêtage (clipping) | Pas de headroom | Vérifier `master_volume` et `true_peak_limit` |
| Basses absentes | High-pass trop agressif | Baisser `voice_highpass_freq` à 60 Hz |
| Voix nasale | Presence boost trop fort | Baisser `voice_presence_boost` à 1 dB |

### 14.3 Synchronisation

| Problème | Cause | Mitigation |
|----------|-------|------------|
| Audio en retard sur la vidéo | Sidechain qui décale | Utiliser frame-by-frame au lieu de sidechain |
| Désync progressive | Taux d'échantillonnage différent | Forcer `-ar 48000` sur toutes les pistes |
| Audio qui se coupe avant la fin | Durée du mix trop courte | SyncGuard avec `auto_correct` et apad |
| Double piste audio | Mux qui conserve l'ancienne piste | `-map` explicite pour ne garder que la nouvelle |

**Règle d'or** : Toujours valider la sync après chaque étape avec `SyncGuard.verify_muxed_video()`. Comparer les durées audio et vidéo. L'offset doit être < 40 ms.

### 14.4 Performance

| Problème | Cause | Mitigation |
|----------|-------|------------|
| Téléchargement lent | Fichiers WAV volumineux | Streaming download, cache local |
| Sidechain lent | Filtre complexe FFmpeg | Utiliser preview mode pour itérer |
| Mix master lent | 3+ pistes à mixer | Paralléliser les étapes indépendantes |
| Cache qui gonfle | Nombreuses itérations | `invalidate()` périodique, taille max configurable |

### 14.5 Epidemic Sound — Limitations MCP

| Limitation | Impact | Contournement |
|------------|--------|--------------|
| Pas d'API de génération de playlist | Choix manuel du meilleur morceau | Algorithme `select_best_match()` avec scoring |
| Nombre de téléchargements limité | Impossible de tout pré-cacher | Cache des IDs + stockage local |
| SFX pas toujours disponibles pour concepts rares | SFX manquant | Générateur placeholder FFmpeg |
| Latence de recherche (1-3s) | Pipeline ralenti | Timeout long (30s), cache des résultats |

### 14.6 Autres pièges

| Piège | Symptôme | Solution |
|-------|----------|----------|
| Chemins absolus vs relatifs | FFmpeg ne trouve pas les fichiers | Toujours convertir en absolu avant d'appeler FFmpeg |
| Nombre pair d'échantillons requis | Erreur codec | Forcer `ceil(n/2)*2` sur les durées |
| Caractères spéciaux dans les chemins | FFmpeg échoue | `shlex.quote()` sur tous les chemins |
| Volume master trop bas | Vidéo trop silencieuse | Vérifier `master_volume` et `voice_normalization_target` |
| Ducking qui ne se déclenche pas | Seuil trop bas | Vérifier `ducking_threshold` et les niveaux de la voix |
| SFX qui se chevauchent | Bouillie sonore | `_resolve_temporal_conflicts()` avec intervalle minimum |
| Musique trop courte | Silence en fin de vidéo | Activer `music_loop` |
| Fichiers WAV temporaires non nettoyés | Disque saturé | Nettoyage du cache après chaque run |

---

## 15. Tests

### 15.1 Tests unitaires

```python
# tests/test_voice_pipeline.py
class TestVoicePipeline:
    """Tests du pipeline de traitement vocal."""

    def test_extract_from_video(self):
        """Vérifie l'extraction audio depuis une vidéo."""
        pipeline = VoicePipeline(AudioConfig())
        result = await pipeline._extract_from_video(TEST_VIDEO)
        assert result.exists()
        # Vérifier le format : WAV, 48kHz, stéréo
        probe = await ffprobe(str(result))
        assert probe["streams"][0]["codec_name"] == "pcm_s16le"
        assert probe["streams"][0]["sample_rate"] == "48000"

    def test_highpass_filter(self):
        """Vérifie que le high-pass coupe bien les basses fréquences."""
        pipeline = VoicePipeline(AudioConfig(voice_highpass_freq=80.0))
        # Tester avec un signal synthétique contenant 50Hz
        result = pipeline._apply_highpass(SYNTHETIC_50HZ_FILE)
        # Vérifier que l'amplitude à 50Hz est réduite
        ...

    def test_compression_reduces_dynamic_range(self):
        """Vérifie que le compresseur réduit la dynamique."""
        pipeline = VoicePipeline(AudioConfig(
            voice_compression_ratio=4.0,
            voice_compression_threshold=-18.0,
        ))
        original_rms = compute_rms(TEST_VOICE_FILE)
        compressed = pipeline._apply_compression(TEST_VOICE_FILE)
        compressed_rms = compute_rms(compressed)
        # Le RMS compressé devrait être plus élevé (moins de dynamique)
        assert compressed_rms > original_rms

    def test_normalization_target_lufs(self):
        """Vérifie que la normalisation atteint la cible LUFS."""
        pipeline = VoicePipeline(AudioConfig(
            voice_normalization_target=-16.0,
        ))
        result = pipeline._apply_normalization(TEST_VOICE_FILE, OUTPUT_FILE)
        lufs = measure_integrated_loudness(result)
        assert abs(lufs - (-16.0)) < 1.0  # Tolérance 1 LUFS

    def test_pipeline_complete(self):
        """Test du pipeline vocal complet."""
        pipeline = VoicePipeline(AudioConfig())
        result = await pipeline.process(TEST_VIDEO, OUTPUT_FILE)
        assert result.exists()
        assert result.stat().st_size > 0


# tests/test_music_engine.py
class TestMusicEngine:
    """Tests du moteur de musique."""

    def test_mood_mapping(self):
        """Vérifie le mapping mood → Epidemic moods."""
        moods = MusicEngine._mood_to_epidemic_moods("energetic")
        assert "energetic" in moods
        assert "upbeat" in moods

    def test_bpm_score_perfect(self):
        """Score BPM parfait = 1.0."""
        score = MusicEngine._score_bpm_match(120.0, 120.0)
        assert score == 1.0

    def test_bpm_score_different(self):
        """Score BPM différent = réduit."""
        score = MusicEngine._score_bpm_match(100.0, 120.0)
        assert score < 1.0
        assert score > 0.0

    def test_duration_score_enough(self):
        """Durée suffisante = score 1.0."""
        score = MusicEngine._score_duration_match(120.0, 60.0)
        assert score == 1.0

    def test_duration_score_short(self):
        """Durée insuffisante = score < 1.0."""
        score = MusicEngine._score_duration_match(30.0, 60.0)
        assert score == 0.5

    def test_select_best_match(self):
        """Vérifie la sélection du meilleur résultat."""
        results = [
            EpidemicSearchResult(id="1", title="A", moods=["energetic"], duration=60, bpm=120),
            EpidemicSearchResult(id="2", title="B", moods=["calm"], duration=30, bpm=80),
        ]
        engine = MusicEngine.__new__(MusicEngine)
        best = engine.select_best_match(results, "energetic", 120, 60)
        assert best.id == "1"


# tests/test_sfx_engine.py
class TestSFXEngine:
    """Tests du moteur d'effets sonores."""

    def test_suggest_transitions(self):
        """Vérifie la suggestion de SFX pour les transitions."""
        edit_meta = EditMetadata(scene_changes=[5.0, 10.0, 15.0], total_duration=20.0)
        engine = SFXEngine.__new__(SFXEngine)
        suggestions = engine._suggest_transitions(edit_meta)
        assert len(suggestions) == 3
        assert all(s.category == "transition" for s in suggestions)
        assert suggestions[0].start_time == 4.85  # 5.0 - 0.15

    def test_suggest_accent_words(self):
        """Vérifie la suggestion d'accents sur mots-clés."""
        edit_meta = EditMetadata(
            speech_segments=[
                {"start": 0.0, "end": 3.0, "text": "C'est très important de comprendre"},
            ],
            total_duration=10.0,
        )
        engine = SFXEngine.__new__(SFXEngine)
        suggestions = engine._suggest_accent_words(edit_meta)
        assert len(suggestions) >= 1
        assert "important" in suggestions[0].id

    def test_limit_sfx_per_minute(self):
        """Vérifie la limitation du nombre de SFX par minute."""
        engine = SFXEngine.__new__(SFXEngine)
        engine.config = AudioConfig(sfx_max_per_minute=3)
        suggestions = [SoundEffect(id=f"sfx_{i}", ...) for i in range(20)]
        limited = engine._limit_sfx_per_minute(suggestions, 60.0)
        assert len(limited) <= 3

    def test_resolve_temporal_conflicts(self):
        """Vérifie la résolution des conflits temporels."""
        engine = SFXEngine.__new__(SFXEngine)
        engine.config = AudioConfig(sfx_min_interval=0.5)
        overlapping = [
            SoundEffect(id="a", start_time=0.0, duration=0.5, confidence=0.9, ...),
            SoundEffect(id="b", start_time=0.3, duration=0.5, confidence=0.8, ...),
        ]
        resolved = engine._resolve_temporal_conflicts(overlapping)
        assert len(resolved) == 1  # Un seul gardé

    def test_placeholder_generation(self):
        """Vérifie la génération d'SFX placeholder."""
        engine = SFXEngine.__new__(SFXEngine)
        sfx = SoundEffect(id="test", concept="test", duration=0.5, ...)
        result = engine._generate_placeholder_sfx(sfx, TMP_DIR)
        assert Path(result.local_path).exists()


# tests/test_ducking.py
class TestDuckingEngine:
    """Tests du moteur de ducking."""

    def test_build_ducking_curve(self):
        """Vérifie la construction de la courbe ducking."""
        engine = DuckingEngine(AudioConfig(
            ducking_level=-10.0,
            ducking_attack=0.1,
            ducking_release=0.3,
        ))
        segments = [
            {"start": 2.0, "end": 5.0},
            {"start": 8.0, "end": 10.0},
        ]
        curve = engine._build_ducking_curve(segments)

        # Vérifier les points clés
        assert len(curve) >= 6  # 2 segments × 3 points (pre, sustain, post)

        # Segment 1 : pre-roll à 1.9 (2.0 - 0.1)
        assert any(p.time == 1.9 and p.gain_db == 0.0 for p in curve)

        # Segment 1 : sustain à 2.0 (début parole)
        assert any(p.time == 2.0 and p.gain_db == -10.0 for p in curve)

        # Segment 1 : fin sustain à 5.0
        assert any(p.time == 5.0 and p.gain_db == -10.0 for p in curve)

        # Segment 1 : post-roll à 5.3 (5.0 + 0.3)
        assert any(p.time == 5.3 and p.gain_db == 0.0 for p in curve)

    def test_db_to_linear(self):
        """Vérifie la conversion dB → facteur linéaire."""
        assert abs(DuckingEngine._db_to_linear(0.0) - 1.0) < 0.001
        assert abs(DuckingEngine._db_to_linear(-6.0) - 0.5) < 0.001
        assert abs(DuckingEngine._db_to_linear(-20.0) - 0.1) < 0.01

    def test_curve_to_ffmpeg_expr(self):
        """Vérifie la génération d'expression FFmpeg."""
        engine = DuckingEngine(AudioConfig())
        curve = [
            DuckingFrame(time=0.0, gain_db=0.0),
            DuckingFrame(time=1.0, gain_db=-6.0),
            DuckingFrame(time=2.0, gain_db=0.0),
        ]
        expr = engine._curve_to_ffmpeg_expr(curve)
        assert "if(lt(t,1.0)" in expr
        assert "if(lt(t,2.0)" in expr


# tests/test_sync_guard.py
class TestSyncGuard:
    """Tests du SyncGuard."""

    def test_verify_synced_video(self):
        """Vérifie qu'une vidéo synchrone passe le test."""
        guard = SyncGuard(AudioConfig(sync_tolerance_ms=40))
        report = await guard.verify_muxed_video(SYNCED_TEST_VIDEO)
        assert report.synced
        assert report.offset_ms < 40.0

    def test_verify_desynced_video(self):
        """Vérifie qu'une vidéo désynchronisée échoue."""
        guard = SyncGuard(AudioConfig(sync_tolerance_ms=40))
        report = await guard.verify_muxed_video(DESYNCED_TEST_VIDEO)
        assert not report.synced
        assert report.offset_ms > 40.0

    def test_auto_correct_adds_silence(self):
        """Vérifie que la correction ajoute du silence si audio trop court."""
        guard = SyncGuard(AudioConfig(sync_tolerance_ms=10, sync_auto_correct=True))
        result = await guard.auto_correct(
            TEST_VIDEO_10S,
            SHORT_AUDIO_8S,
            OUTPUT_FILE,
        )
        # Vérifier que la durée est maintenant correcte
        report = await guard.verify_muxed_video(result)
        assert report.synced

    def test_auto_correct_trims(self):
        """Vérifie que la correction tronque si audio trop long."""
        guard = SyncGuard(AudioConfig(sync_tolerance_ms=10, sync_auto_correct=True))
        result = await guard.auto_correct(
            TEST_VIDEO_10S,
            LONG_AUDIO_15S,
            OUTPUT_FILE,
        )
        report = await guard.verify_muxed_video(result)
        assert report.synced

    def test_parse_time_base(self):
        """Vérifie le parsing du time_base."""
        assert SyncGuard._parse_time_base("1/1000") == 0.001
        assert SyncGuard._parse_time_base("1/90000") == 1 / 90000


# tests/test_epidemic_client.py
class TestEpidemicClient:
    """Tests du client MCP Epidemic Sound (mockés)."""

    async def test_search_music(self, mocker):
        """Vérifie la recherche de musique."""
        mock_response = {
            "results": [
                {
                    "id": "track_001",
                    "title": "Upbeat Tech",
                    "artist": "Epidemic Artist",
                    "duration": 120.0,
                    "bpm": 120,
                    "moods": ["energetic", "upbeat"],
                    "genres": ["electronic"],
                }
            ]
        }
        mocker.patch("httpx.AsyncClient.get",
                      return_value=MockResponse(200, mock_response))

        client = EpidemicSoundMCPClient(api_key="test_key")
        results = await client.search_music(
            query="tech tutorial",
            mood=["energetic"],
            bpm_min=100,
            bpm_max=140,
        )
        assert len(results) == 1
        assert results[0].title == "Upbeat Tech"
        assert results[0].bpm == 120

    async def test_download_track(self, mocker):
        """Vérifie le téléchargement d'un morceau."""
        mocker.patch("httpx.AsyncClient.get",
                      return_value=MockResponse(200, {"download_url": "https://..."}))
        mocker.patch("httpx.AsyncClient.stream",
                      return_value=MockAsyncStream())

        client = EpidemicSoundMCPClient(api_key="test_key")
        result = await client.download_track("track_001", TMP_FILE)
        assert result.exists()


# tests/test_mix_engine.py
class TestMixEngine:
    """Tests du moteur de mix final."""

    def test_mix_three_tracks(self):
        """Vérifie le mix de 3 pistes en une."""
        engine = MixEngine(AudioConfig())
        result = await engine.mix(
            voice_path=TEST_VOICE,
            music_path=TEST_MUSIC,
            sfx_paths=[TEST_SFX],
            output_path=OUTPUT_MIX,
        )
        assert result.exists()
        # Vérifier que le fichier a la bonne durée
        probe = await ffprobe(str(result))
        assert float(probe["format"]["duration"]) > 0

    def test_stems_export(self):
        """Vérifie l'export des stems séparés."""
        engine = MixEngine(AudioConfig(export_stems=True))
        stems = await engine.export_stems(
            voice_path=TEST_VOICE,
            music_path=TEST_MUSIC,
            sfx_paths=[TEST_SFX],
            output_dir=STEMS_DIR,
        )
        assert stems["voice"].exists()
        assert stems["music"].exists()
        assert stems["sfx"].exists()
        assert stems["master"].exists()
```

### 15.2 Tests d'intégration

```python
# tests/test_integration.py
class TestFullAudioPipeline:
    """Test d'intégration complet du pipeline audio."""

    TEST_VIDEO = Path(__file__).parent / "fixtures" / "test_video_10s.mp4"
    TEST_METADATA = Path(__file__).parent / "fixtures" / "sample_edit_metadata.json"
    TEST_TRANSCRIPT = Path(__file__).parent / "fixtures" / "sample_transcript.json"

    async def test_full_pipeline_preview(self):
        """Pipeline complet en mode preview."""
        pipeline = AudioPipeline()
        config = AudioConfig(
            music_search_enabled=False,   # Pas d'appel API en test
            sfx_enabled=False,
            export_stems=False,
            work_dir=str(TMP_DIR),
        )
        report = await pipeline.run(
            montage_video=self.TEST_VIDEO,
            edit_metadata_path=self.TEST_METADATA,
            transcript_path=self.TEST_TRANSCRIPT,
            config=config,
            mode="preview",
        )
        assert report.output_path.exists()
        assert report.voice_processed
        assert report.sync_ok
        assert report.sync_offset_ms < config.sync_tolerance_ms

    async def test_full_pipeline_with_mock_epidemic(self):
        """Pipeline complet avec MCP mocké."""
        pipeline = AudioPipeline()
        config = AudioConfig(
            music_search_enabled=True,
            sfx_enabled=True,
            export_stems=True,
            work_dir=str(TMP_DIR),
        )
        # Mock du client Epidemic
        with patch("agent4_audio.epidemic_client.EpidemicSoundMCPClient") as mock:
            mock.return_value.search_music.return_value = [
                EpidemicSearchResult(id="mock_1", title="Mock", duration=30, moods=["calm"])
            ]
            mock.return_value.select_best_match.return_value = ...
            mock.return_value.download_track.return_value = TEST_MUSIC

            report = await pipeline.run(
                montage_video=self.TEST_VIDEO,
                edit_metadata_path=self.TEST_METADATA,
                transcript_path=self.TEST_TRANSCRIPT,
                config=config,
                mode="final",
            )

        assert report.output_path.exists()
        assert report.music_applied
        assert report.sfx_count >= 0
        assert report.stems_path is not None

    async def test_sync_through_pipeline(self):
        """Vérifie que la sync est maintenue tout au long du pipeline."""
        pipeline = AudioPipeline()
        config = AudioConfig(
            music_search_enabled=False,
            sfx_enabled=False,
            ducking_enabled=True,
            work_dir=str(TMP_DIR),
        )
        report = await pipeline.run(
            montage_video=self.TEST_VIDEO,
            edit_metadata_path=self.TEST_METADATA,
            transcript_path=self.TEST_TRANSCRIPT,
            config=config,
            mode="final",
        )
        # Vérifier que la sync est bonne en sortie
        guard = SyncGuard(config)
        final_check = await guard.verify_muxed_video(Path(report.output_path))
        assert final_check.synced, f"Sync fail: offset={final_check.offset_ms}ms"

    async def test_ducking_audible_effect(self):
        """Vérifie que le ducking est effectivement appliqué (analyse RMS)."""
        # Comparer le RMS de la musique seule vs musique + voix avec ducking
        pipeline = AudioPipeline()
        config = AudioConfig(
            music_search_enabled=False,
            sfx_enabled=False,
            ducking_enabled=True,
            ducking_level=-12.0,
            work_dir=str(TMP_DIR),
        )
        report = await pipeline.run(
            montage_video=self.TEST_VIDEO,
            edit_metadata_path=self.TEST_METADATA,
            transcript_path=self.TEST_TRANSCRIPT,
            config=config,
            mode="final",
        )
        # Analyser le RMS dans les zones de parole vs silence
        rms_analysis = analyze_rms_by_segments(
            Path(report.output_path),
            speech_segments=self.TEST_METADATA["speech_segments"],
        )
        # Le RMS devrait être plus bas pendant la parole (musique duckée)
        assert rms_analysis["speech_rms"] < rms_analysis["silence_rms"]
```

### 15.3 Scénarios de test

| # | Scénario | Description | Résultat attendu |
|---|----------|-------------|------------------|
| 1 | Pipeline complet preview | Vidéo 10s, config preview | Vidéo produite < 30s |
| 2 | Pipeline complet final | Vidéo 10s, config final | Vidéo produite avec stems |
| 3 | Voice only | Pas de musique ni SFX | Seulement voix nettoyée |
| 4 | Ducking désactivé | `ducking_enabled=false` | Musique au même volume partout |
| 5 | Sync automatique | Audio tronqué/allongé | Correction appliquée |
| 6 | Epidemic Sound down | API retourne 503 | Fallback voice-only |
| 7 | SFX conflict | SFX qui se chevauchent | Résolution propre |
| 8 | Cache hit | Même config 2× | Deuxième exécution plus rapide |
| 9 | Aucun speech_segment | Métadonnées vides | Ducking basé sur transcript |
| 10 | Musique trop courte | Durée < vidéo | Loop ou silence en fin |

---

## Annexes

### A. Dépendances Python

```txt
# requirements.txt
pydantic>=2.7.0
typer>=0.9.0
httpx>=0.27.0
numpy>=1.26.0
soundfile>=0.12.0
audioread>=3.0.0
pydub>=0.25.0
# Optionnel : analyse audio avancée
# librosa>=2.0.0
# scipy>=1.12.0
```

### B. Dépendances système

```dockerfile
# Dockerfile.agent4
FROM python:3.11-slim

# FFmpeg (nécessaire pour tout le pipeline)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY src/agent4_audio/ .
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "agent4_audio.cli"]
```

### C. Exemple d'edit_metadata.json (entrée)

```json
{
  "schema_version": "1.0",
  "source_cutlist": "/data/cutlists/cutlist_interview.json",
  "total_duration": 94.64,
  "segments": [
    {
      "montage_start": 0.0,
      "montage_end": 12.5,
      "original_start": 0.0,
      "original_end": 12.5,
      "text": "Bienvenue dans cette vidéo sur l'architecture des microservices."
    },
    {
      "montage_start": 12.5,
      "montage_end": 25.0,
      "original_start": 15.2,
      "original_end": 27.8,
      "text": "Comme vous pouvez le voir, chaque service est indépendant."
    }
  ],
  "pace": "medium",
  "beat_per_minute_estimate": 110.0,
  "scene_changes": [0.0, 12.5, 25.0, 40.0, 65.0],
  "mood": "educational",
  "speech_segments": [
    {"start": 0.0, "end": 3.2, "text": "Bienvenue dans cette vidéo"},
    {"start": 3.5, "end": 12.5, "text": "sur l'architecture des microservices."},
    {"start": 12.5, "end": 25.0, "text": "Comme vous pouvez le voir, chaque service est indépendant."}
  ]
}
```

### D. Exemple de sortie audio_metadata.json

```json
{
  "schema_version": "2.0",
  "source_edit": "/data/cutlists/edit_metadata.json",
  "source_video": "/data/audio/montage_audio.mp4",
  "tracks": [
    {
      "type": "voice",
      "source": "extracted",
      "start": 0.0,
      "end": 94.64,
      "volume_db": 0.0,
      "ducking_applied": false
    },
    {
      "type": "music",
      "source": "epidemic_sound",
      "track_id": "es_track_45231",
      "title": "Uplifting Tech Beat",
      "start": 0.0,
      "end": 94.64,
      "volume_db": -6.0,
      "ducking_applied": true
    },
    {
      "type": "sfx",
      "source": "epidemic_sound",
      "track_id": "es_sfx_7821",
      "title": "Whoosh Transition",
      "start": 12.35,
      "end": 12.85,
      "volume_db": -3.0,
      "ducking_applied": false
    }
  ],
  "master_volume_db": -1.0,
  "peak_level_db": -2.3,
  "rms_level_db": -18.5,
  "loudness_lufs": -14.2,
  "loudness_range": 8.5,
  "true_peak": -1.8,
  "music_epidemic_id": "es_track_45231",
  "music_title": "Uplifting Tech Beat",
  "music_artist": "Epidemic Artist",
  "music_bpm": 112.0,
  "music_key": "C major",
  "music_mood": ["uplifting", "focused"],
  "music_match_score": 0.87,
  "sfx_count": 5,
  "sfx_categories": {
    "transition": 3,
    "accent": 1,
    "cinematic": 1
  },
  "ducking_applied": true,
  "ducking_level_db": -12.0,
  "voice_processing": {
    "noise_reduction": true,
    "compression": true,
    "eq": true,
    "normalization": true
  },
  "sync_offset_ms": 12.0,
  "sync_ok": true,
  "pipeline_duration_ms": 28450,
  "errors": [],
  "warnings": []
}
```

### E. Schéma récapitulatif du pipeline audio

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             AGENT #4 — DESIGN AUDIO                                  │
│                                                                                     │
│  montage_rendu.mp4  ──────────────────────────────────────────────────────┐        │
│  edit_metadata.json ───┐                                                    │        │
│  transcript.json    ───┤                                                    │        │
│  config.yaml        ───┘                                                    │        │
│                                                                             ▼        │
│  ┌──────────────────────────────────────────────────────────────────────────┐      │
│  │                         Orchesterateur                                     │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │      │
│  │  │  Voice   │  │  Music   │  │   SFX    │  │  Ducking │  │  Master  │   │      │
│  │  │ Pipeline │──▶│ Engine   │──▶│ Engine   │──▶│ Engine   │──▶│  Mix    │──▶│──▶ montage_audio.mp4
│  │  │          │  │          │  │          │  │          │  │          │   │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │      │
│  │       │              │              │              │           │         │      │
│  │       ▼              ▼              ▼              ▼           ▼         │      │
│  │  voice_cleaned  music_backgrnd  sfx_master    ducking_curve  master_mix │      │
│  │    .wav            .wav           .wav          .json          .wav     │      │
│  └──────────────────────────────────────────────────────────────────────────┘      │
│       │                                                                             │
│       ▼                                                                             │
│  ┌──────────┐                                                                      │
│  │Sync Guard│  → Vérification obligatoire avant livraison                           │
│  └──────────┘                                                                      │
│       │                                                                             │
│       ├── Synced → audio_metadata.json + montage_audio.mp4 → Agent #5              │
│       └── Desync → Correction auto ou AudioSyncError                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

> **Document créé le 08/07/2026 — Agent #4 Design Audio v4.0.0**
> Dernière mise à jour : 08/07/2026
