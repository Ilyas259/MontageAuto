# Agent #3 — Montage & Animation

> **Module responsable de l'assemblage final de la vidéo** : découpage source, composition des plans (facecam, split-screen, full B-roll), transitions, sous-titres, et rendu final.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture du module](#2-architecture-du-module)
3. [Pipeline d'exécution](#3-pipeline-dexécution)
4. [Modèles de données (Pydantic)](#4-modèles-de-données-pydantic)
5. [Configuration externalisable](#5-configuration-externalisable)
6. [Templates de composition](#6-templates-de-composition)
7. [Algorithme de placement des B-rolls](#7-algorithme-de-placement-des-b-rolls)
8. [Système de sous-titres](#8-système-de-sous-titres)
9. [Opérations FFmpeg](#9-opérations-ffmpeg)
10. [Intégration Hyperframes / Remotion](#10-intégration-hyperframes--remotion)
11. [Interface CLI](#11-interface-cli)
12. [Mode Preview](#12-mode-preview)
13. [Boucle Qualité (Agent #5)](#13-boucle-qualité-agent-5)
14. [Structure du module](#14-structure-du-module)
15. [Pièges connus & mitigations](#15-pièges-connus--mitigations)
16. [Tests](#16-tests)

---

## 1. Vue d'ensemble

### 1.1 Mission

Prendre la `cut_list.json` (segments à garder + suggestions B-roll) et le `script_cleaned.txt` produits par l'Agent #2, et produire une vidéo montée, animée, sous-titrée, prête pour l'Agent #4 (Design Audio).

### 1.2 Entrées / Sorties

```
Entrées :
  ├── cut_list.json          ← Agent #2  (segments, timecodes, types, B-rolls)
  ├── script_cleaned.txt     ← Agent #2  (texte parlé nettoyé)
  ├── source_video.mp4       ← Agent #1  (vidéo brute originale)
  ├── source_audio.wav       ← Agent #1  (piste audio extraite, optionnelle)
  └── config.yaml            ← Agent #6  (paramètres de montage)

Sorties :
  ├── video_montage_preview.mp4   (version basse résolution, rapide)
  ├── video_montage_final.mp4     (version finale HD)
  └── montage_report.json         (métadonnées de rendu pour Agent #5)
```

### 1.3 Stack technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11+ | Orchestrateur, logique métier |
| Pydantic | 2.7+ | Schémas de config & templates |
| FFmpeg | 7.0+ | Découpage, concaténation, encodage |
| Hyperframes | latest (payant) | Compositions motion design complexes (canonique) |
| Remotion | 4.x (open source) | Fallback open source si Hyperframes indisponible |
| Node.js | 20+ | Runtime pour Hyperframes/Remotion |
| Puppeteer | latest | Headless Chromium pour rendu (Remotion) |

---

## 2. Architecture du module

```
┌────────────────────────────────────────────────────────────┐
│                   Agent #3 Orchestrator                     │
│  (orchestrator.py)                                         │
│  Lit la config, charge cut_list.json, pilote le pipeline   │
└───┬──────────┬──────────┬──────────┬──────────┬────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
│FFmpeg  │ │Template│ │B-roll  │ │Sous-   │ │ Hyperframes /│
│Ops     │ │Engine  │ │Placer  │ │titres  │ │ Remotion     │
│découpe │ │facecam │ │algo    │ │karaoke │ │ Renderer     │
│concat  │ │split   │ │overlay │ │block   │ │ (fallback)   │
│encodage│ │full    │ │mix     │ │timing  │ │              │
└────────┘ │broll   │ └────────┘ └────────┘ └──────────────┘
           │transit │
           └────────┘
                │
                ▼
         ┌──────────────┐
         │  Preview /   │
         │  Final       │
         │  Encoder     │
         └──────────────┘
```

### 2.1 Flux de données détaillé

```
cut_list.json
    │
    ▼
┌─────────────────────┐
│ Parse & Validate    │ ← Pydantic models
│ segments, brolls    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ FFmpeg: découpage   │ ← Extraire chaque segment source
│ des segments bruts  │    en fichiers temporaires
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Assignation template │ ← facecam / split / full_broll
│ par segment         │    selon type dans cut_list
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Placement B-rolls   │ ← Algorithme de placement
│ aux timestamps      │    (voir §7)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Composition         │ ← Appel Hyperframes (ou Remotion)
│ motion design       │    pour chaque segment composé
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Concaténation +     │ ← FFmpeg concat demuxer
│ transitions         │ + filtres de transition
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Sous-titres         │ ← Burn-in du texte
│ (burn-in)           │    karaoke ou block
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Encodage final      │ ← H.264 / H.265 / Preview
└──────┬──────────────┘
       │
       ▼
  montage_report.json
  video_montage_final.mp4
```

---

## 3. Pipeline d'exécution

### 3.1 Orchestrateur

```python
class MontagePipeline:
    """Orchestre l'ensemble du pipeline de montage."""

    async def run(
        self,
        cut_list_path: Path,
        script_path: Path,
        source_video: Path,
        config: MontageConfig,
        mode: Literal["preview", "final"] = "final",
    ) -> MontageReport:
        # 1. Parse inputs
        cut_list = self._load_cut_list(cut_list_path)
        script = self._load_script(script_path)

        # 2. Extract audio reference for sync
        audio_ref = await self._extract_audio_reference(source_video)

        # 3. Segment extraction
        segments = await self._extract_segments(
            source_video, cut_list.segments, config.work_dir
        )

        # 4. Template assignment
        composed = await self._compose_segments(
            segments, cut_list, script, config
        )

        # 5. B-roll integration
        composed = await self._place_brolls(
            composed, cut_list.broll_suggestions, config
        )

        # 6. Render compositions
        rendered = await self._render_compositions(
            composed, config, mode
        )

        # 7. Concat with transitions
        final = await self._concatenate(
            rendered, config, mode
        )

        # 8. Burn subtitles
        final = await self._burn_subtitles(
            final, script, config
        )

        # 9. Build report
        return self._build_report(final, segments, config)
```

### 3.2 Gestion des étapes

Chaque étape est un module indépendant avec :
- Entrée/sortie typée (Pydantic)
- Gestion d'erreur → fallback ou crash explicite
- Cache des fichiers temporaires (pour reprise après crash)
- Logging structuré (JSON lines)

---

## 4. Modèles de données (Pydantic)

### 4.1 cut_list.json — Schéma d'entrée

```python
class BrollPlacement(BaseModel):
    """Suggestion de B-roll venant de l'Agent #2."""
    start_time: float          # Timestamp d'apparition (secondes)
    end_time: float            # Timestamp de disparition
    concept: str               # Description visuelle (ex: "diagramme architecture")
    placement: Literal["overlay", "fullscreen", "split"]
    priority: int = 5          # 1-10 (10 = critique)
    source: Literal["generated", "stock", "library", "none"] = "generated"
    asset_path: str | None     # Chemin vers l'asset si déjà disponible


class CutSegment(BaseModel):
    """Segment vidéo à conserver dans le montage final."""
    id: str                    # Identifiant unique (ex: "seg_001")
    start_time: float          # Début dans la source (secondes)
    end_time: float            # Fin dans la source
    type: Literal["facecam", "split", "full_broll", "transition"]
    transcript: str            # Texte parlé dans ce segment
    brolls: list[BrollPlacement] = []
    transition_out: Literal["cut", "fade", "slide", "zoom"] = "cut"


class CutList(BaseModel):
    """Contrat d'entrée principal depuis l'Agent #2."""
    segments: list[CutSegment]
    broll_suggestions: list[BrollPlacement]
    metadata: dict = {}
```

### 4.2 Templates de composition

```python
class CompositionTemplate(BaseModel):
    """Template de composition pour un segment."""
    name: str
    type: Literal["facecam", "split", "full_broll", "transition"]
    layout: dict = {}
    """Positions CSS des éléments. Structure dépend du type :
       facecam:  {"speaker": {"x": 0, "y": 0, "w": 1, "h": 1}}
                 -> speaker peut être positionné via facecam_position
       split:    {"speaker": {"x": 0, "y": 0, "w": 0.5, "h": 1},
                  "broll":   {"x": 0.5, "y": 0, "w": 0.5, "h": 1}}
       full_broll: {"broll": {"x": 0, "y": 0, "w": 1, "h": 1}}
                 -> voix off superposée
    """
    animation: dict = {}
    """Animations d'entrée/sortie :
       {"entry": {"type": "fade_in", "duration": 0.3},
        "exit":  {"type": "fade_out", "duration": 0.3},
        "speaker_breathe": {"type": "scale_pulse", "intensity": 0.02}}
    """
    default_duration: float = 5.0
    subtitle_position: Literal["bottom", "top", "center"] = "bottom"


class ComposedSegment(BaseModel):
    """Segment après assignation d'un template et placement B-roll."""
    segment_id: str
    template: CompositionTemplate
    source_clip: Path             # Fichier extrait par FFmpeg
    broll_clips: list[Path] = [] # Assets B-roll résolus
    broll_placements: list[BrollPlacement] = []
    subtitle_events: list[SubtitleEvent] = []
    output_path: Path | None = None
```

### 4.3 Événements de sous-titres

```python
class SubtitleEvent(BaseModel):
    """Un mot ou groupe de mots à afficher."""
    text: str
    start_time: float
    end_time: float
    word_index: int = 0
    is_highlighted: bool = False  # Pour karaoke : mot en cours


class SubtitleConfig(BaseModel):
    style: Literal["karaoke", "block", "none"] = "block"
    font: str = "Inter"
    font_size: int = 28
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    position: Literal["bottom", "top", "center"] = "bottom"
    margin_bottom: int = 60
    max_width_pct: float = 0.85       # 85% de l'écran max
    line_height: float = 1.4
    # Paramètres karaoke uniquement
    karaoke_highlight_color: str = "#FFD700"
    karaoke_advance_mode: Literal["word", "char"] = "word"
```

### 4.4 Rapport de montage

```python
class SegmentRenderInfo(BaseModel):
    segment_id: str
    source_range: tuple[float, float]
    template_type: str
    duration: float
    brolls_applied: int
    render_success: bool
    render_duration_ms: float
    output_path: str
    errors: list[str] = []


class MontageReport(BaseModel):
    pipeline_version: str = "3.0.0"
    source_video: str
    total_segments: int
    total_duration: float
    segments: list[SegmentRenderInfo]
    brolls_total: int
    brolls_placed: int
    transitions_applied: list[str]
    subtitle_style: str
    render_mode: str
    total_render_time_ms: float
    output_path: str
    preview_path: str | None = None
    quality_feedback: list[dict] = []  # Rempli par Agent #5
    errors: list[str] = []
```

---

## 5. Configuration externalisable

Fichier `config.yaml` — chargé par l'Orchestrator (Agent #6) et passé à Agent #3 :

```yaml
montage:
  # Résolution et fps
  output_resolution: "1920x1080"     # "1920x1080" | "3840x2160" | "1280x720"
  fps: 30

  # Transitions par défaut
  transition_default: "cut"          # cut | fade | slide | zoom
  transition_duration: 0.3           # secondes

  # Sous-titres
  subtitle_style: "block"            # karaoke | block | none
  subtitle_font: "Inter"
  subtitle_font_size: 28
  subtitle_color: "#FFFFFF"
  subtitle_stroke_color: "#000000"

  # B-rolls
  b_roll_transition: "fade"          # fade | slide | cut
  min_broll_duration: 2.0            # durée minimum en secondes
  max_broll_duration: 15.0           # durée maximum (évite les B-rolls trop longs)
  broll_search_paths:                # Où chercher les assets B-roll
    - "/data/brolls/library"
    - "/data/brolls/generated"

  # Facecam (incrustation)
  facecam_position: "bottom-right"   # bottom-right | bottom-left | top-right | top-left
  facecam_size: 0.25                 # fraction de l'écran (0.0 - 1.0)
  facecam_corner_radius: 12          # coins arrondis en pixels
  facecam_shadow: true               # ombre portée
  facecam_border: false

  # Performance
  preview_scale: 0.5                 # Résolution preview = 50%
  preview_fps: 15
  max_concurrent_renders: 2          # Rendu parallèle max
  cache_dir: "/tmp/agent3_cache"

  # Encodage
  codec: "h264"                      # h264 | h265 | h264_nvenc (si GPU)
  crf: 23                            # Qualité (0-51, plus bas = meilleur)
  preset: "medium"                   # ultrafast | fast | medium | slow | veryslow
  audio_codec: "aac"
  audio_bitrate: "192k"

  # Feedback loop (Agent #5)
  max_iterations: 3
  auto_apply_feedback: true
```

### 5.1 Validation Pydantic

```python
from pydantic import BaseModel, Field, model_validator
from typing import Literal


class MontageConfig(BaseModel):
    output_resolution: str = "1920x1080"
    fps: int = 30
    transition_default: Literal["cut", "fade", "slide", "zoom"] = "cut"
    transition_duration: float = 0.3
    subtitle_style: Literal["karaoke", "block", "none"] = "block"
    subtitle_font: str = "Inter"
    subtitle_font_size: int = 28
    subtitle_color: str = "#FFFFFF"
    subtitle_stroke_color: str = "#000000"
    b_roll_transition: Literal["fade", "slide", "cut"] = "fade"
    min_broll_duration: float = 2.0
    max_broll_duration: float = 15.0
    broll_search_paths: list[str] = ["/data/brolls/library", "/data/brolls/generated"]
    facecam_position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
    facecam_size: float = Field(default=0.25, ge=0.05, le=1.0)
    facecam_corner_radius: int = 12
    facecam_shadow: bool = True
    facecam_border: bool = False
    preview_scale: float = Field(default=0.5, ge=0.1, le=1.0)
    preview_fps: int = 15
    max_concurrent_renders: int = 2
    cache_dir: str = "/tmp/agent3_cache"
    codec: Literal["h264", "h265", "h264_nvenc", "h265_nvenc"] = "h264"
    crf: int = Field(default=23, ge=0, le=51)
    preset: Literal["ultrafast", "fast", "medium", "slow", "veryslow"] = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    max_iterations: int = 3
    auto_apply_feedback: bool = True

    @model_validator(mode="after")
    def validate_resolution(self):
        parts = self.output_resolution.split("x")
        if len(parts) != 2:
            raise ValueError("output_resolution must be WxH (e.g. 1920x1080)")
        w, h = int(parts[0]), int(parts[1])
        if w % 2 != 0 or h % 2 != 0:
            raise ValueError("Resolution dimensions must be even for codec compliance")
        return self

    @property
    def preview_resolution(self) -> str:
        w, h = self.output_resolution.split("x")
        pw = int(int(w) * self.preview_scale)
        ph = int(int(h) * self.preview_scale)
        # Ensure even dimensions
        pw = pw if pw % 2 == 0 else pw + 1
        ph = ph if ph % 2 == 0 else ph + 1
        return f"{pw}x{ph}"

    @property
    def has_gpu(self) -> bool:
        return "nvenc" in self.codec
```

---

## 6. Templates de composition

### 6.1 Catalogue des templates

Chaque template est un fichier Python indépendant dans `templates/`.

#### 6.1.1 Facecam

```python
# templates/facecam.py
from agent3_montage.models import CompositionTemplate

FACECAM_DEFAULT = CompositionTemplate(
    name="facecam_default",
    type="facecam",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            # Le speaker prend tout l'écran en arrière-plan
            # La position effective est définie par facecam_position
        },
        # Optionnel : overlay décoratif
        "overlay": {
            "type": "gradient_mesh",
            "opacity": 0.15,
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.2},
        "exit": {"type": "fade_out", "duration": 0.2},
        "speaker_breathe": {
            "type": "scale_pulse",
            "intensity": 0.01,       # Micro-respiration
            "period": 4.0,           # Secondes
        },
    },
    default_duration=10.0,
    subtitle_position="bottom",
)

FACECAM_GREENSCREEN = CompositionTemplate(
    name="facecam_greenscreen",
    type="facecam",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "chroma_key": True,      # Active le chroma key
            "chroma_key_color": "#00FF00",
        },
        "background": {
            "type": "solid",
            "color": "#1a1a2e",
            "gradient": "radial",    # Subtle radial gradient background
        },
    },
    animation={
        "entry": {"type": "slide_in_right", "duration": 0.4},
        "exit": {"type": "fade_out", "duration": 0.3},
    },
    default_duration=10.0,
    subtitle_position="bottom",
)
```

**Rendu FFmpeg / Hyperframes** :

- **Approche simple (FFmpeg)** : Redimensionner la vidéo source à la position configurée avec `scale=iw*0.25:ih*0.25` + overlay positionné selon `facecam_position`. Fond uni ou gradient généré.
- **Approche Hyperframes** : Template React/HTML avec `<video>` en CSS `object-fit: cover`, overlay gradient, animations CSS `@keyframes breathe`.

#### 6.1.2 Split Screen

```python
# templates/split.py
SPLIT_50_50 = CompositionTemplate(
    name="split_50_50",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 0.5, "h": 1,
            "alignment": "center",
        },
        "broll": {
            "x": 0.5, "y": 0, "w": 0.5, "h": 1,
            "fit": "cover",
        },
        "divider": {
            "type": "line",
            "x": 0.5, "y": 0.05, "w": 2, "h": 0.9,
            "color": "rgba(255,255,255,0.3)",
        },
    },
    animation={
        "entry": {"type": "split_reveal", "duration": 0.4},
        "exit": {"type": "fade_out", "duration": 0.2},
    },
    default_duration=8.0,
    subtitle_position="bottom",
)

SPLIT_70_30 = CompositionTemplate(
    name="split_70_30_speaker",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 0.7, "h": 1,
        },
        "broll": {
            "x": 0.7, "y": 0, "w": 0.3, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.3},
        "exit": {"type": "fade_out", "duration": 0.3},
    },
    default_duration=8.0,
    subtitle_position="bottom",
)
```

#### 6.1.3 Full B-roll

```python
# templates/full_broll.py
FULL_BROLL_DEFAULT = CompositionTemplate(
    name="full_broll_default",
    type="full_broll",
    layout={
        "broll": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
            "ken_burns": True,       # Effet Ken Burns léger
        },
        "text_overlay": {
            "x": 0, "y": 0.75, "w": 1, "h": 0.2,
            "type": "text",
            "alignment": "center",
            "opacity": 0.9,
        },
    },
    animation={
        "entry": {"type": "ken_burns_in", "duration": 0.5},
        "exit": {"type": "fade_out", "duration": 0.3},
        "ken_burns": {
            "zoom_start": 1.0,
            "zoom_end": 1.05,
            "pan": "center",         # center | left | right
        },
    },
    default_duration=5.0,
    subtitle_position="center",      # Sous-titres au centre sur B-roll
)
```

#### 6.1.4 Transitions

```python
# templates/transitions.py
TRANSITION_CUT = CompositionTemplate(
    name="transition_cut",
    type="transition",
    layout={},                       # Pas de layout, cut pur
    animation={},                    # Pas d'animation
    default_duration=0.0,
    subtitle_position="bottom",
)

TRANSITION_FADE = CompositionTemplate(
    name="transition_fade",
    type="transition",
    layout={},
    animation={
        "type": "crossfade",
        "duration": 0.3,
    },
    default_duration=0.3,
    subtitle_position="bottom",
)

TRANSITION_SLIDE = CompositionTemplate(
    name="transition_slide",
    type="transition",
    layout={
        "direction": "left",         # left | right | up | down
    },
    animation={
        "type": "slide",
        "duration": 0.4,
        "easing": "cubic-bezier(0.25, 0.1, 0.25, 1.0)",
    },
    default_duration=0.4,
    subtitle_position="bottom",
)

TRANSITION_ZOOM = CompositionTemplate(
    name="transition_zoom",
    type="transition",
    layout={
        "zoom_direction": "in",      # in | out
    },
    animation={
        "type": "zoom_blur",
        "duration": 0.5,
        "blur_max": 15,              # Pixels de blur au pic
    },
    default_duration=0.5,
    subtitle_position="bottom",
)
```

### 6.2 Template Engine

```python
class TemplateEngine:
    """Moteur qui résout et applique les templates aux segments."""

    _registry: dict[str, CompositionTemplate] = {}

    @classmethod
    def register(cls, template: CompositionTemplate):
        cls._registry[template.name] = template

    @classmethod
    def resolve(cls, segment: CutSegment, config: MontageConfig) -> CompositionTemplate:
        """Sélectionne le template approprié pour un segment."""
        base = cls._get_default_for_type(segment.type)

        if segment.type == "facecam":
            return cls._apply_facecam_position(base, config)
        elif segment.type == "split":
            return cls._adjust_split_ratio(base, segment)
        elif segment.type == "full_broll":
            return cls._apply_ken_burns(base, segment)

        return base

    @classmethod
    def _get_default_for_type(cls, seg_type: str) -> CompositionTemplate:
        mapping = {
            "facecam": FACECAM_DEFAULT,
            "split": SPLIT_50_50,
            "full_broll": FULL_BROLL_DEFAULT,
            "transition": TRANSITION_CUT,
        }
        return copy.deepcopy(mapping[seg_type])

    @staticmethod
    def _apply_facecam_position(
        template: CompositionTemplate, config: MontageConfig
    ) -> CompositionTemplate:
        """Ajuste la position du speaker selon la config."""
        positions = {
            "bottom-right": (1 - config.facecam_size - 0.02, 1 - config.facecam_size - 0.02),
            "bottom-left": (0.02, 1 - config.facecam_size - 0.02),
            "top-right": (1 - config.facecam_size - 0.02, 0.02),
            "top-left": (0.02, 0.02),
        }
        x, y = positions[config.facecam_position]
        template.layout["speaker"]["x"] = x
        template.layout["speaker"]["y"] = y
        template.layout["speaker"]["w"] = config.facecam_size
        template.layout["speaker"]["h"] = config.facecam_size * (9/16)  # Ratio 16:9
        return template
```

---

## 7. Algorithme de placement des B-rolls

### 7.1 Principes

1. **Priorité** : Les B-rolls de priorité haute (8-10) sont toujours placés.
2. **Espacement** : Deux B-rolls ne peuvent pas se chevaucher à moins d'être de placement `overlay`.
3. **Durée** : Chaque B-roll dure au minimum `min_broll_duration` et au maximum `max_broll_duration`.
4. **Contexte** : Un B-roll `fullscreen` remplace la vidéo du speaker ; un `overlay` se superpose ; un `split` partage l'écran.
5. **Transition** : L'apparition des B-rolls utilise `b_roll_transition`.

### 7.2 Algorithme

```python
class BrollPlacer:
    """
    Algorithme de placement des B-rolls dans la timeline.

    Stratégie :
    1. Filtrer et trier les suggestions par priorité décroissante
    2. Grouper par segment
    3. Pour chaque segment, placer les B-rolls selon leur placement :
       - fullscreen : remplit tout l'écran → le segment devient type full_broll
       - overlay : caler par-dessus la facecam/split
       - split : le segment devient type split
    4. Résoudre les conflits temporels
    5. Assigner les assets disponibles
    """

    def __init__(self, config: MontageConfig):
        self.config = config
        self.broll_cache: dict[str, Path] = {}

    def place(
        self,
        segments: list[CutSegment],
        suggestions: list[BrollPlacement],
    ) -> list[ComposedSegment]:
        # 1. Filtrer les suggestions valides
        valid = self._filter_valid(suggestions)

        # 2. Trier par priorité (décroissante)
        valid.sort(key=lambda b: b.priority, reverse=True)

        # 3. Assigner aux segments
        segment_map = {s.id: s for s in segments}
        composed = []

        for segment in segments:
            seg_brolls = [b for b in valid
                          if b.start_time >= segment.start_time
                          and b.end_time <= segment.end_time]
            seg_brolls = self._resolve_overlaps(seg_brolls, segment)
            composed.append(self._build_composed(segment, seg_brolls))

        return composed

    def _filter_valid(self, suggestions: list[BrollPlacement]) -> list[BrollPlacement]:
        """Filtre les suggestions invalides ou trop courtes."""
        valid = []
        for b in suggestions:
            duration = b.end_time - b.start_time
            if duration < self.config.min_broll_duration:
                # Étendre la durée si possible pour respecter le minimum
                b.end_time = b.start_time + self.config.min_broll_duration
            if b.end_time - b.start_time > self.config.max_broll_duration:
                # Tronquer si trop long
                b.end_time = b.start_time + self.config.max_broll_duration
            valid.append(b)
        return valid

    def _resolve_overlaps(
        self,
        brolls: list[BrollPlacement],
        segment: CutSegment,
    ) -> list[BrollPlacement]:
        """
        Résout les conflits temporels entre B-rolls :
        - Deux fullscreen ne peuvent pas coexister → garder le plus prioritaire
        - overlay peut coexister avec fullscreen/split
        - split peut coexister avec facecam
        """
        if len(brolls) <= 1:
            return brolls

        # Séparer par type de placement
        overlays = [b for b in brolls if b.placement == "overlay"]
        fullscreens = [b for b in brolls if b.placement == "fullscreen"]
        splits = [b for b in brolls if b.placement == "split"]

        # Pour les fullscreens en conflit, garder le plus prioritaire
        resolved_fs = self._deduplicate_overlapping(fullscreens)

        # Pour les splits en conflit, garder le plus prioritaire
        resolved_sp = self._deduplicate_overlapping(splits)

        # Overlays peuvent tous coexister
        return resolved_fs + resolved_sp + overlays

    def _deduplicate_overlapping(
        self, brolls: list[BrollPlacement]
    ) -> list[BrollPlacement]:
        """Si des B-rolls se chevauchent, garder le plus prioritaire."""
        if len(brolls) <= 1:
            return brolls

        brolls = sorted(brolls, key=lambda b: b.priority, reverse=True)
        result = [brolls[0]]

        for b in brolls[1:]:
            # Pas de chevauchement avec déjà placés ? Ajouter
            can_place = all(
                b.start_time >= placed.end_time or b.end_time <= placed.start_time
                for placed in result
            )
            if can_place:
                result.append(b)

        return result
```

### 7.3 Résolution des assets

```python
class BrollAssetResolver:
    """Résout les chemins des assets B-roll."""

    def __init__(self, search_paths: list[Path]):
        self.search_paths = search_paths
        self._index: dict[str, list[Path]] = {}

    async def resolve(self, broll: BrollPlacement) -> Path | None:
        """Trouve l'asset le plus pertinent pour une suggestion B-roll."""
        # 1. Si déjà un chemin explicite
        if broll.asset_path and Path(broll.asset_path).exists():
            return Path(broll.asset_path)

        # 2. Chercher par concept dans les dossiers configurés
        for base_path in self.search_paths:
            candidates = await self._search_by_concept(base_path, broll.concept)
            if candidates:
                return candidates[0]

        # 3. Fallback : générer une image placeholder
        return await self._generate_placeholder(broll)

    async def _search_by_concept(
        self, base: Path, concept: str
    ) -> list[Path]:
        """Recherche par mot-clé dans le dossier d'assets."""
        # Implémentation : scanner les fichiers et matcher par nom/métadonnées
        results = []
        if not base.exists():
            return results
        for f in base.glob("*"):
            if concept.lower() in f.stem.lower():
                results.append(f)
        return sorted(results)[:3]

    async def _generate_placeholder(self, broll: BrollPlacement) -> Path:
        """Génère une image/vidéo placeholder avec le texte du concept."""
        # Utiliser FFmpeg drawtext ou ImageMagick
        output = Path(self.cache_dir) / f"broll_placeholder_{hash(broll.concept)}.mp4"
        # Commande FFmpeg : couleur unie + texte centré
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=#1a1a2e:s=1920x1080:d=5",
            "-vf", f"drawtext=text='{broll.concept}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            str(output),
        ]
        await asyncio.create_subprocess_exec(*cmd)
        return output
```

---

## 8. Système de sous-titres

### 8.1 Modes supportés

| Mode | Description | Rendu | Performances |
|------|-------------|-------|-------------|
| `block` | Texte complet affiché en bloc, centré, multi-lignes | FFmpeg drawtext | Rapide |
| `karaoke` | Mot par mot, surlignage synchro | Hyperframes/Remotion + timer JS | Modéré |
| `none` | Pas de sous-titres | — | — |

### 8.2 Algorithme de synchronisation

```python
class SubtitleEngine:
    """
    Génère les événements de sous-titres à partir du script nettoyé
    et des timecodes des segments.
    """

    def __init__(self, config: SubtitleConfig):
        self.config = config

    def generate_events(
        self,
        script: str,
        segments: list[CutSegment],
        words_timings: list[dict] | None = None,
    ) -> list[list[SubtitleEvent]]:
        """
        Génère les événements de sous-titres pour chaque segment.

        Deux modes :
        - words_timings fourni : synchronisation mot-à-mot (karaoke-ready)
        - sans timings : répartition uniforme du texte sur la durée du segment (block)
        """
        events_by_segment = []
        for segment in segments:
            if words_timings:
                events = self._generate_karaoke(segment, words_timings)
            else:
                events = self._generate_block(segment)
            events_by_segment.append(events)
        return events_by_segment

    def _generate_block(
        self, segment: CutSegment
    ) -> list[SubtitleEvent]:
        """Mode bloc : tout le texte du segment en une fois."""
        duration = segment.end_time - segment.start_time
        return [
            SubtitleEvent(
                text=segment.transcript,
                start_time=segment.start_time + 0.1,  # Petit délai
                end_time=segment.end_time - 0.1,
                word_index=0,
                is_highlighted=False,
            )
        ]

    def _generate_karaoke(
        self,
        segment: CutSegment,
        words_timings: list[dict],
    ) -> list[SubtitleEvent]:
        """Mode karaoke : un événement par mot avec timestamp."""
        seg_words = [
            w for w in words_timings
            if segment.start_time <= w["start"] < segment.end_time
        ]
        events = []
        for i, word in enumerate(seg_words):
            events.append(
                SubtitleEvent(
                    text=word["text"],
                    start_time=word["start"],
                    end_time=word["end"],
                    word_index=i,
                    is_highlighted=False,
                )
            )
        return events

    def render_block_ffmpeg(
        self,
        video_path: Path,
        events: list[SubtitleEvent],
        output_path: Path,
        resolution: tuple[int, int],
    ) -> Path:
        """
        Rendu des sous-titres en mode block via FFmpeg drawtext.

        Utilise un filtre drawtext avec le texte complet positionné en bas.
        """
        w, h = resolution
        font = self.config.font
        fontsize = self.config.font_size
        color = self.config.color
        stroke = self.config.stroke_color
        stroke_w = self.config.stroke_width

        # Construction du filtre drawtext pour chaque événement
        filter_parts = []
        for i, evt in enumerate(events):
            # Échapper le texte pour FFmpeg
            text = evt.text.replace("'", "'\\\\\\''").replace(":", "\\:")
            # Timecode : enable entre start et end
            enable = f"between(t,{evt.start_time:.3f},{evt.end_time:.3f})"

            # Position
            if self.config.position == "bottom":
                y = f"h-{self.config.margin_bottom}"
            elif self.config.position == "top":
                y = f"{self.config.margin_bottom}"
            else:  # center
                y = f"(h-text_h)/2"

            filter_parts.append(
                f"drawtext=text='{text}'"
                f":fontfile={font}"
                f":fontsize={fontsize}"
                f":fontcolor={color}"
                f":borderw={stroke_w}"
                f":bordercolor={stroke}"
                f":x=(w-text_w)/2"
                f":y={y}"
                f":enable='{enable}'"
            )

        if not filter_parts:
            return video_path

        # Combiner les filtres
        vf = ",".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:a", "copy",
            str(output_path),
        ]
        # Exécution synchrone
        return output_path

    def render_karaoke_hyperframes(
        self,
        events: list[SubtitleEvent],
        composition_dir: Path,
    ) -> dict:
        """
        Génère les données de sous-titres karaoke pour le template Hyperframes.

        Retourne un dictionnaire JSON qui sera injecté dans le template React.
        """
        return {
            "type": "karaoke",
            "font": self.config.font,
            "font_size": self.config.font_size,
            "color": self.config.color,
            "highlight_color": self.config.karaoke_highlight_color,
            "advance_mode": self.config.karaoke_advance_mode,
            "words": [
                {
                    "text": e.text,
                    "start": e.start_time,
                    "end": e.end_time,
                    "index": e.word_index,
                }
                for e in events
            ],
        }
```

### 8.3 Comparaison karaoke vs block

| Critère | Karaoke | Block |
|---------|---------|-------|
| Engagement | Élevé | Moyen |
| Complexité rendu | Haute (JS timer) | Faible (drawtext) |
| Synchronisation | Mot à mot | Par segment |
| Performance | Lourd (30+ FPS JS) | Léger (1 drawtext/seg) |
| Attendu YouTube | ✅ Standard | ✅ Acceptable |
| Accessibilité | Meilleure | Standard |

---

## 9. Opérations FFmpeg

### 9.1 Découpage des segments

```python
class FFmpegOps:
    """Opérations FFmpeg bas niveau."""

    @staticmethod
    async def extract_segment(
        source: Path,
        start: float,
        end: float,
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Extrait un segment de la source avec timecodes précis.

        Utilise la méthode 'copy stream copy' pour éviter le ré-encodage
        sur les segments bruts. Le ré-encodage n'aura lieu qu'à la composition.
        """
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),           # Seek avant (rapide avec -noaccurate_seek)
            "-i", str(source),
            "-t", str(duration),
            "-c", "copy",                 # Stream copy : pas de ré-encodage
            "-avoid_negative_ts", "make_zero",
            str(output),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise FFmpegError(f"Segment extraction failed: {stderr.decode()}")
        return output

    @staticmethod
    async def extract_segment_accurate(
        source: Path,
        start: float,
        end: float,
        output: Path,
    ) -> Path:
        """
        Extraction précise avec ré-encodage pour les coupes exactes.

        À utiliser quand la précision à la frame est critique (split, overlay).
        """
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-ss", str(start),           # Seek après input = plus précis
            "-t", str(duration),
            "-c:v", "libx264",
            "-crf", "18",                 # Haute qualité pour sous-composition
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            str(output),
        ]
        # ... execution
        return output
```

### 9.2 Concaténation avec transitions

```python
    @staticmethod
    async def concat_with_transitions(
        segments: list[Path],
        transitions: list[CompositionTemplate],
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Concatène les segments avec transitions.

        Utilise le concat demuxer (sans transitions) comme fallback rapide,
        ou le filter complex pour les transitions fondu/slide/zoom.
        """
        if all(t.name == "transition_cut" for t in transitions):
            return await FFmpegOps._concat_simple(segments, output)
        else:
            return await FFmpegOps._concat_with_filters(
                segments, transitions, output, config
            )

    @staticmethod
    async def _concat_simple(
        segments: list[Path], output: Path
    ) -> Path:
        """Concaténation simple sans transitions (concat demuxer)."""
        # Créer le fichier de liste
        list_file = output.parent / "concat_list.txt"
        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg.absolute()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output),
        ]
        # ... execution
        return output

    @staticmethod
    async def _concat_with_filters(
        segments: list[Path],
        transitions: list[CompositionTemplate],
        output: Path,
        config: MontageConfig,
    ) -> Path:
        """
        Concaténation avec transitions via filter complex.

        Chaque transition est un overlay temporel entre la fin du segment N
        et le début du segment N+1 avec fondu/slide/zoom.
        """
        # Construction du graphe de filtre complex FFmpeg
        # Exemple pour des fondus enchaînés :
        # [0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[out]
        # Avec transitions : xfade filter
        filter_parts = []
        for i, seg in enumerate(segments):
            filter_parts.append(f"[{i}:v][{i}:a]")

        concat_filter = (
            f"concat=n={len(segments)}:v=1:a=1[vout][aout]"
        )

        cmd = [
            "ffmpeg", "-y",
        ]
        for seg in segments:
            cmd.extend(["-i", str(seg)])

        # Xfade pour transitions
        xfade_parts = []
        for i, trans in enumerate(transitions):
            if i >= len(segments) - 1:
                break
            if trans.name == "transition_fade":
                xfade_parts.append(
                    f"xfade=transition=fade:duration={trans.default_duration}:offset=..."
                )

        # Final filtergraph
        if xfade_parts:
            vf = ";".join(xfade_parts)
        else:
            vf = concat_filter

        cmd.extend(["-filter_complex", vf])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", config.codec, "-crf", str(config.crf)])
        cmd.extend(["-c:a", config.audio_codec, "-b:a", config.audio_bitrate])
        cmd.append(str(output))

        # ... execution
        return output
```

### 9.3 Désync audio : prévention et détection

```python
class AudioSyncGuard:
    """
    Vérifie et prévient la désynchronisation audio.

    Causes connues de désync :
    - Utilisation de -ss après -i (précis mais lent) vs avant -i (rapide mais risque de désync)
    - Changements de frame rate entre source et rendu
    - Concaténation de clips avec des codecs audio différents
    - Extraction de segments sans -copyts
    """

    @staticmethod
    def safe_extract_cmd(source: Path, start: float, duration: float, output: Path) -> list[str]:
        """
        Commande FFmpeg sécurisée contre la désync.

        Règles d'or :
        1. Toujours mettre -ss avant -i pour les coupes rapides
        2. Utiliser -copyts pour préserver les timestamps originaux
        3. Ré-encoder l'audio (pas de copy) si on change le framerate
        4. Vérifier l'échantillonnage audio identique entre clips
        """
        return [
            "ffmpeg", "-y",
            "-ss", str(start),           # Seek avant input = rapide
            "-i", str(source),
            "-t", str(duration),
            "-copyts",                    # Préserver les timestamps
            "-async", "1",                # Resync audio si nécessaire
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "aresample=async=1:first_pts=0",  # Force resync audio
            str(output),
        ]

    @staticmethod
    def detect_sync_offset(video_path: Path) -> float:
        """
        Détecte le décalage audio/vidéo en analysant les timestamps.

        Utilise FFprobe pour comparer les premiers pts audio et vidéo.
        Retourne l'offset en ms (>0 = audio en avance).
        """
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(video_path),
        ]
        # ... analyser les start_pts audio vs vidéo
        return 0.0  # Placeholder
```

### 9.4 Encodage final

```python
    @staticmethod
    async def encode_final(
        input_path: Path,
        output_path: Path,
        config: MontageConfig,
    ) -> Path:
        """Encodage final de la vidéo montée."""
        codec_map = {
            "h264": "libx264",
            "h265": "libx265",
            "h264_nvenc": "h264_nvenc",
            "h265_nvenc": "hevc_nvenc",
        }
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", codec_map[config.codec],
            "-crf", str(config.crf),
            "-preset", config.preset,
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            "-movflags", "+faststart",  # Streaming optimisé
            str(output_path),
        ]
        # ... execution
        return output_path

    @staticmethod
    async def encode_preview(
        input_path: Path,
        output_path: Path,
        config: MontageConfig,
    ) -> Path:
        """Version preview rapide et légère."""
        pw, ph = config.preview_resolution.split("x")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"scale={pw}:{ph}",
            "-r", str(config.preview_fps),
            "-c:v", "libx264",
            "-crf", "28",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        # ... execution
        return output_path
```

---

## 10. Intégration Hyperframes / Remotion

### 10.1 Architecture du renderer

```
┌────────────────────────────────────────────────────┐
│                AbstractRenderer                     │
│  Interface commune pour Hyperframes & Remotion     │
├────────────────────────────────────────────────────┤
│  + render(composition: CompositionConfig) → Path   │
│  + render_preview(composition) → Path              │
│  + is_available() → bool                           │
└───────────────────┬────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────────┐  ┌──────────────────┐
│ HyperframesRenderer│  │ RemotionRenderer  │
│ (canonique)       │  │ (fallback OSS)    │
├──────────────────┤  ├──────────────────┤
│ API HTTP          │  │ Node.js process   │
│ Timeline intégrée  │  │ Puppeteer         │
│ Payant (Agen)     │  │ Open source       │
└──────────────────┘  └──────────────────┘
```

### 10.2 AbstractRenderer

```python
class CompositionConfig(BaseModel):
    """Configuration de composition passée au renderer."""
    template: CompositionTemplate
    segments: list[ComposedSegment]
    subtitles: dict
    config: MontageConfig
    output_path: Path
    mode: Literal["preview", "final"] = "final"


class AbstractRenderer(ABC):
    """Interface commune pour le rendu de compositions."""

    @abstractmethod
    async def render(self, composition: CompositionConfig) -> Path:
        """Rend la composition complète."""
        ...

    @abstractmethod
    async def render_preview(self, composition: CompositionConfig) -> Path:
        """Rend une preview rapide."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Vérifie si le renderer est disponible."""
        ...

    @abstractmethod
    async def get_version(self) -> str:
        """Retourne la version du renderer."""
        ...
```

### 10.3 HyperframesRenderer

```python
class HyperframesRenderer(AbstractRenderer):
    """
    Renderer utilisant Hyperframes (par Agen).

    Hyperframes est un service HTTP (localhost:3000 par défaut) qui
    transforme du HTML/CSS/JS en vidéo. Il expose :
    - POST /api/compose : créer une composition
    - GET /api/status/:id : statut du rendu
    - GET /api/download/:id : télécharger la vidéo
    - PUT /api/timeline : modifier la timeline manuellement

    Avantages :
    - Timeline interactive intégrée
    - Rendu accéléré (WebGL)
    - Templates React prêts à l'emploi

    Inconvénients :
    - Produit payant (licence Agen)
    - Dépendance externe
    """

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def is_available(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def render(self, composition: CompositionConfig) -> Path:
        """
        Envoie la composition à Hyperframes.

        Convertit nos templates Pydantic en payload JSON
        attendu par l'API Hyperframes.
        """
        payload = self._build_payload(composition)
        resp = await self.client.post(
            f"{self.base_url}/api/compose",
            json=payload,
        )
        resp.raise_for_status()
        job_id = resp.json()["id"]

        # Poll jusqu'à completion
        while True:
            status = await self.client.get(
                f"{self.base_url}/api/status/{job_id}"
            )
            data = status.json()
            if data["status"] == "completed":
                break
            elif data["status"] == "failed":
                raise HyperframesError(data.get("error", "Unknown error"))
            await asyncio.sleep(2)

        # Download
        download = await self.client.get(
            f"{self.base_url}/api/download/{job_id}"
        )
        composition.output_path.write_bytes(download.content)
        return composition.output_path

    def _build_payload(self, composition: CompositionConfig) -> dict:
        """Convertit notre modèle en payload Hyperframes."""
        return {
            "resolution": composition.config.output_resolution,
            "fps": composition.config.fps,
            "tracks": [
                self._segment_to_track(s, composition.config)
                for s in composition.segments
            ],
            "subtitles": composition.subtitles,
            "output": {
                "format": "mp4",
                "codec": composition.config.codec,
            },
        }

    def _segment_to_track(
        self, segment: ComposedSegment, config: MontageConfig
    ) -> dict:
        """Convertit un ComposedSegment en piste Hyperframes."""
        return {
            "type": "video",
            "src": str(segment.source_clip),
            "layout": segment.template.layout,
            "animation": segment.template.animation,
            "brolls": [
                {
                    "src": str(b),
                    "placement": p.placement,
                    "transition": config.b_roll_transition,
                }
                for b, p in zip(segment.broll_clips, segment.broll_placements)
            ],
        }
```

### 10.4 RemotionRenderer (Fallback)

```python
class RemotionRenderer(AbstractRenderer):
    """
    Renderer fallback utilisant Remotion (open source).

    Remotion est une bibliothèque React qui permet de créer des vidéos
    par programmation. Nécessite Node.js + Puppeteer.

    Architecture :
    - Génère des fichiers React (JSX) à partir de nos templates
    - Les rend via Puppeteer (headless Chromium)
    - Assemble les frames en vidéo via FFmpeg

    Dépendances lourdes :
    - Node.js 20+
    - Puppeteer (~300MB Chromium)
    - @remotion/bundler, @remotion/renderer
    """

    TEMPLATE_DIR = Path(__file__).parent / "remotion_templates"

    def __init__(self, node_path: str = "node"):
        self.node_path = node_path
        self._check_node()

    def _check_node(self):
        """Vérifie que Node.js et les packages Remotion sont disponibles."""
        # Lancer `node -e "require('@remotion/renderer')"` pour vérifier
        pass

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.node_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def render(self, composition: CompositionConfig) -> Path:
        """
        Rendu via Remotion.

        Étapes :
        1. Générer le fichier de composition React
        2. Bundler le projet Remotion
        3. Rendre les frames avec Puppeteer
        4. Assembler en vidéo avec FFmpeg (Remotion le fait automatiquement)
        """
        # 1. Générer le template React
        template_path = await self._generate_react_template(composition)

        # 2. Lancer le rendu Remotion
        cmd = [
            self.node_path,
            str(self.TEMPLATE_DIR / "render.mjs"),
            "--input", str(template_path),
            "--output", str(composition.output_path),
            "--resolution", composition.config.output_resolution,
            "--fps", str(composition.config.fps),
        ]
        if composition.mode == "preview":
            cmd.extend(["--quality", "low"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RemotionError(f"Remotion render failed: {stderr.decode()}")

        return composition.output_path

    async def _generate_react_template(
        self, composition: CompositionConfig
    ) -> Path:
        """
        Génère un fichier React (JSX) à partir de nos templates Pydantic.

        Convertit les templates en composants React avec :
        - <AbsoluteFill> pour le fond
        - <Video> ou <Img> pour les médias
        - <Sequence> pour les segments temporels
        - CSS-in-JS pour les animations
        - <spring> ou <interpolate> pour les transitions
        """
        output = self.TEMPLATE_DIR / "_generated" / f"edit_{uuid4().hex}.tsx"
        output.parent.mkdir(parents=True, exist_ok=True)

        # Générer le code JSX
        jsx_lines = [
            'import { AbsoluteFill, Video, Sequence, useCurrentFrame, interpolate, spring } from "remotion";',
            'import React from "react";',
            "",
            f"export const Edit: React.FC = () => {{",
            f"  const frame = useCurrentFrame();",
            "  return (",
            "    <AbsoluteFill style={{ backgroundColor: '#000' }}>",
        ]

        for segment in composition.segments:
            jsx_lines.extend(self._segment_to_jsx(segment, composition.config))

        jsx_lines.extend([
            "    </AbsoluteFill>",
            "  );",
            "};",
        ])

        output.write_text("\n".join(jsx_lines))
        return output

    def _segment_to_jsx(
        self, segment: ComposedSegment, config: MontageConfig
    ) -> list[str]:
        """Convertit un segment en JSX React/Remotion."""
        lines = []
        dur_frames = int(segment.template.default_duration * config.fps)

        if segment.template.type == "facecam":
            lines.append(
                f'      <Sequence durationInFrames={dur_frames}>'
            )
            lines.append(
                f'        <Video src="{segment.source_clip}" '
                f'style={{'
                f'  position: "absolute",'
                f'  width: "{config.facecam_size * 100}%",'
                f'  ...positionConfig("{config.facecam_position}")'
                f'}} />'
            )
            lines.append('      </Sequence>')

        elif segment.template.type == "split":
            lines.append(
                f'      <Sequence durationInFrames={dur_frames}>'
            )
            lines.append(
                f'        <Video src="{segment.source_clip}" '
                f'style={{{{width: "50%", left: 0}}}} />'
            )
            if segment.broll_clips:
                lines.append(
                    f'        <Video src="{segment.broll_clips[0]}" '
                    f'style={{{{width: "50%", left: "50%"}}}} />'
                )
            lines.append('      </Sequence>')

        return lines

    async def get_version(self) -> str:
        return "4.x (Remotion OSS)"
```

### 10.5 Détection et fallback

```python
class RendererFactory:
    """
    Factory qui détecte le renderer disponible.

    Ordre de préférence :
    1. Hyperframes (si service disponible)
    2. Remotion (si Node.js + packages dispo)
    3. FFmpeg-only (fallback ultime : pas de compositions complexes)
    """

    @staticmethod
    async def create() -> AbstractRenderer:
        # Tester Hyperframes
        hf = HyperframesRenderer()
        if await hf.is_available():
            logger.info("🎬 Using Hyperframes renderer (canonical)")
            return hf

        # Tester Remotion
        rm = RemotionRenderer()
        if await rm.is_available():
            logger.info("🎬 Using Remotion renderer (fallback OSS)")
            return rm

        # Fallback FFmpeg
        logger.warning("⚠️  No advanced renderer available. Using FFmpeg-only mode.")
        return FFmpegOnlyRenderer()
```

---

## 11. Interface CLI

```bash
# Usage principal
video-automation agent edit --input cut_list.json \
    --script script_cleaned.txt \
    --source source_video.mp4 \
    --config config.yaml \
    --output /output/video_montage_final.mp4

# Mode preview (rapide)
video-automation agent edit --input cut_list.json \
    --script script_cleaned.txt \
    --source source_video.mp4 \
    --preview \
    --output /output/video_montage_preview.mp4

# Sous-titres uniquement (sans refaire le rendu)
video-automation agent edit --burn-subtitles \
    --input video_montage.mp4 \
    --script script_cleaned.txt \
    --subtitle-style karaoke \
    --output /output/video_subtitled.mp4

# Inspection du plan de montage
video-automation agent edit --plan \
    --input cut_list.json \
    --script script_cleaned.txt \
    --output /output/montage_plan.json

# Résumé des templates disponibles
video-automation agent edit --list-templates

# Mode interactif (sélection des B-rolls)
video-automation agent edit --interactive \
    --input cut_list.json
```

### 11.1 Implémentation CLI (Typer)

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="Agent #3 — Montage & Animation")


@app.command()
def edit(
    input: Path = typer.Option(..., "--input", "-i",
                                help="cut_list.json from Agent #2"),
    script: Path = typer.Option(..., "--script", "-s",
                                 help="script_cleaned.txt from Agent #2"),
    source: Path = typer.Option(..., "--source",
                                 help="Source video file"),
    config: Path = typer.Option("config.yaml", "--config", "-c",
                                 help="Montage configuration file"),
    output: Path = typer.Option("video_montage_final.mp4", "--output", "-o",
                                 help="Output video path"),
    preview: bool = typer.Option(False, "--preview", "-p",
                                  help="Generate low-res preview"),
    subtitle_style: Optional[str] = typer.Option(None,
                                                  "--subtitle-style",
                                                  help="Override subtitle style"),
    plan_only: bool = typer.Option(False, "--plan",
                                    help="Only generate montage plan (no render)"),
):
    """Execute le pipeline de montage complet."""
    asyncio.run(_run_edit(
        input, script, source, config, output, preview, subtitle_style, plan_only
    ))


@app.command()
def list_templates():
    """Liste les templates de composition disponibles."""
    for name, tmpl in TemplateEngine._registry.items():
        typer.echo(f"  • {tmpl.type:12s}  {name}")
        typer.echo(f"      Duration: {tmpl.default_duration}s")
        typer.echo(f"      Subtitles: {tmpl.subtitle_position}")


@app.command()
def burn_subtitles(
    input: Path = typer.Option(..., "--input", "-i"),
    script: Path = typer.Option(..., "--script", "-s"),
    subtitle_style: str = typer.Option("block", "--subtitle-style"),
    output: Path = typer.Option("video_subtitled.mp4", "--output"),
):
    """Ajoute ou remplace les sous-titres sur une vidéo existante."""
    asyncio.run(_run_burn_subtitles(input, script, subtitle_style, output))


if __name__ == "__main__":
    app()
```

---

## 12. Mode Preview

### 12.1 Objectif

Générer une version **rapide et légère** de la vidéo pour itération rapide sans attendre le rendu final HD.

### 12.2 Stratégie

```python
class PreviewMode:
    """
    Optimisations pour le mode preview :

    1. Résolution réduite (50% = 960x540)
    2. Framerate réduit (15 fps au lieu de 30)
    3. Codec ultrafast (libx264 preset ultrafast, CRF 28)
    4. Pas de transitions complexes (cut seulement)
    5. Pas de karaoke (block seulement)
    6. Durée max limitée (optionnelle)
    7. Parallélisation des segments courts

    Timing estimé : 2-5min pour une vidéo de 10min (vs 15-30min en full)
    """
```

### 12.3 Cache

```python
class RenderCache:
    """Cache les segments rendus pour éviter de re-rendre."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_segment(self, segment_id: str, config_hash: str) -> Path | None:
        """Vérifie si un segment a déjà été rendu avec la même config."""
        cached = self.cache_dir / f"{segment_id}_{config_hash}.mp4"
        return cached if cached.exists() else None

    def save_segment(self, segment_id: str, config_hash: str, path: Path) -> Path:
        """Sauvegarde un segment rendu dans le cache."""
        dest = self.cache_dir / f"{segment_id}_{config_hash}.mp4"
        shutil.copy2(path, dest)
        return dest

    def invalidate(self, segment_id: str | None = None):
        """Invalide le cache (partiel ou total)."""
        if segment_id:
            for f in self.cache_dir.glob(f"{segment_id}_*.mp4"):
                f.unlink()
        else:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir()
```

---

## 13. Boucle Qualité (Agent #5)

### 13.1 Réception des feedbacks

```python
class QualityFeedback(BaseModel):
    """Feedback de l'Agent #5 (Gemini) sur le rendu."""
    iteration: int
    overall_score: float = Field(ge=0, le=10)
    segments_scores: list[SegmentFeedback] = []
    issues: list[QualityIssue] = []
    suggestions: list[str] = []
    auto_fix: bool = False


class SegmentFeedback(BaseModel):
    segment_id: str
    score: float = Field(ge=0, le=10)
    issues: list[str] = []
    suggested_template: str | None = None


class QualityIssue(BaseModel):
    severity: Literal["critical", "major", "minor", "suggestion"]
    category: str
    description: str
    segment_id: str | None = None
    suggested_action: str | None = None
```

### 13.2 Application automatique des feedbacks

```python
class QualityLoop:
    """
    Boucle d'amélioration continue avec Agent #5.

    Workflow :
    1. Agent #3 rend la vidéo
    2. Envoie le rapport et la vidéo à Agent #5
    3. Agent #5 analyse et retourne QualityFeedback
    4. Agent #3 applique les corrections
    5. Re-rendu (max `max_iterations` fois)
    6. Si auto_apply_feedback=False : marquer pour révision humaine
    """

    def __init__(self, config: MontageConfig, agent5_endpoint: str):
        self.config = config
        self.agent5_client = httpx.AsyncClient(base_url=agent5_endpoint)

    async def run_quality_loop(
        self,
        video_path: Path,
        report: MontageReport,
    ) -> tuple[Path, MontageReport]:
        """Exécute la boucle qualité complète."""

        for iteration in range(self.config.max_iterations):
            # 1. Envoyer à Agent #5 pour analyse
            feedback = await self._request_feedback(video_path, report)

            if not feedback.issues:
                logger.info("✅ Quality check passed!")
                break

            # 2. Appliquer les corrections
            corrections = self._apply_feedback(feedback)

            if not corrections:
                logger.info("No actionable corrections, breaking loop.")
                break

            # 3. Re-rendre
            video_path = await self._rerender(corrections)

            logger.info(f"🔄 Iteration {iteration + 1}/{self.config.max_iterations} done")

        return video_path, report

    def _apply_feedback(
        self, feedback: QualityFeedback
    ) -> list[Correction]:
        """
        Convertit les feedbacks en corrections applicables.

        Exemples de corrections automatiques :
        - "Transition trop rapide" → ajuster transition_duration
        - "Sous-titres trop petits" → augmenter font_size
        - "B-roll trop long" → réduire duration
        - "Mauvaise position facecam" → changer facecam_position
        - "Segment trop sombre" → ajuster brightness/contrast
        - "Désync audio détectée" → ré-extraire avec -copyts
        """
        corrections = []
        for issue in feedback.issues:
            correction = self._issue_to_correction(issue)
            if correction:
                corrections.append(correction)
        return corrections

    def _issue_to_correction(self, issue: QualityIssue) -> Correction | None:
        mapping = {
            "transition_speed": Correction(
                type="config",
                key="transition_duration",
                value=0.5,  # Ralentir
            ),
            "subtitle_size": Correction(
                type="config",
                key="subtitle_font_size",
                value=32,  # Agrandir
            ),
            "broll_duration": Correction(
                type="segment",
                action="adjust_broll_duration",
            ),
            "facecam_position": Correction(
                type="config",
                key="facecam_position",
                value="bottom-left",  # Alternative
            ),
            "audio_sync": Correction(
                type="pipeline",
                action="re_extract_with_sync",
            ),
        }
        return mapping.get(issue.category)
```

### 13.3 Métriques de qualité évaluées par Agent #5

| Catégorie | Métrique | Poids |
|-----------|----------|-------|
| **Visuel** | Composition, éclairage, couleurs | 25% |
| **Audio** | Synchronisation labiale, volume | 20% |
| **Rythme** | Tempo du montage, durée des plans | 20% |
| **Sous-titres** | Lisibilité, synchronisation | 15% |
| **B-rolls** | Pertinence, transitions, durée | 10% |
| **Global** | Impression générale, cohérence | 10% |

---

## 14. Structure du module

```
src/agent3_montage/
├── __init__.py                  # Exports publics, version
├── cli.py                       # Interface CLI (Typer)
├── config.py                    # MontageConfig Pydantic
├── models.py                    # Tous les modèles Pydantic
├── orchestrator.py              # Orchestrateur principal (MontagePipeline)
│
├── templates/                   # Templates de composition
│   ├── __init__.py              # Registre des templates
│   ├── facecam.py               # Templates facecam
│   ├── split.py                 # Templates split screen
│   ├── full_broll.py            # Templates full B-roll
│   └── transitions.py           # Templates de transitions
│
├── ffmpeg_ops.py               # Opérations FFmpeg (découpage, concat, encodage)
├── template_engine.py           # TemplateEngine (résolution/applique)
├── broll_placer.py              # Algorithme de placement B-roll
├── subtitles.py                 # Système de sous-titres
│
├── renderers/                   # Renderers vidéo
│   ├── __init__.py              # RendererFactory
│   ├── base.py                  # AbstractRenderer
│   ├── hyperframes.py           # HyperframesRenderer
│   ├── remotion.py              # RemotionRenderer
│   └── ffmpeg_only.py           # FFmpegOnlyRenderer (fallback ultime)
│
├── quality_loop.py              # Boucle qualité Agent #5
├── preview.py                   # Mode preview
├── cache.py                     # RenderCache
│
├── remotion_templates/          # Templates React pour Remotion
│   ├── package.json
│   ├── render.mjs
│   ├── tsconfig.json
│   └── src/
│       ├── Root.tsx
│       ├── Edit.tsx
│       ├── Facecam.tsx
│       ├── SplitScreen.tsx
│       ├── FullBroll.tsx
│       ├── Subtitles.tsx
│       └── transitions.ts
│
└── tests/
    ├── __init__.py
    ├── test_orchestrator.py
    ├── test_templates.py
    ├── test_broll_placer.py
    ├── test_subtitles.py
    ├── test_ffmpeg_ops.py
    └── test_quality_loop.py
```

---

## 15. Pièges connus & mitigations

### 15.1 Hyperframes est un produit payant — fallback nécessaire

| Problème | Impact | Mitigation |
|----------|--------|------------|
| Hyperframes nécessite une licence Agen | Bloquant si pas de licence | `RendererFactory` détecte Hyperframes → fallback Remotion |
| API Hyperframes peut changer | Break de compatibilité | Versionner l'API contract, tests d'intégration |
| Service Hyperframes doit tourner | Point de défaillance unique | Container Docker séparé, healthcheck, fallback auto |

### 15.2 Remotion nécessite Node.js + Puppeteer

| Problème | Impact | Mitigation |
|----------|--------|------------|
| Puppeteer télécharge Chromium (~300MB) | Build lourd, lent | Pré-installer dans Docker, cache layer |
| Node.js 20+ requis | Version incompatible | `engine-strict` dans package.json |
| Puppeteer peut crasher sans --no-sandbox | Erreur de rendu | Config Docker avec `--no-sandbox` |
| Mémoire : Remotion charge tout en RAM | OOM sur longues vidéos | Découpage par segments, render séquentiel |

### 15.3 FFmpeg peut désync l'audio

| Problème | Cause | Mitigation |
|----------|-------|------------|
| Désync after -ss before -i | FFmpeg ne décode pas les frames de référence | Utiliser `-copyts` + `-async 1` |
| Désync à la concaténation | Codecs audio différents entre segments | Forcer `-c:a aac` sur tous les extraits |
| Désync après transition | Points de montage non alignés sur les keyframes | Ré-encoder les points de transition |
| Désync progressive | Audio drift sur long format | Comparer durée audio vs vidéo après chaque étape |

**Règle d'or** : Toujours valider la sync après chaque étape avec `ffprobe -v quiet -print_format json -show_streams` et comparer `start_pts` des streams audio et vidéo.

### 15.4 Transitions complexes peuvent être saccadées

| Problème | Cause | Mitigation |
|----------|-------|------------|
| Zoom transition stutter | Calcul GPU intensif | Baisser `fps` en preview, utiliser `preset ultrafast` |
| Slide transition jerky | Mauvaise interpolation temporelle | Utiliser `easing: "cubic-bezier"` au lieu de `linear` |
| Crossfade visible banding | 8-bit color depth | Forcer `pix_fmt yuv420p10le` (10-bit) pour les fondus |
| Preview != final render | Différence de résolution | Toujours valider le rendu final à la résolution cible |

### 15.5 Synchronisation labiale

```python
class LipSyncValidator:
    """
    Valide la synchronisation labiale après chaque transformation.

    Utilise FFprobe pour détecter les décalages audio > 50ms.
    """

    THRESHOLD_MS = 50  # Seuil de tolérance

    @staticmethod
    async def validate(video_path: Path) -> SyncReport:
        """Analyse la synchronisation audio/vidéo."""
        probe = await FFmpegOps.probe(video_path)

        audio_stream = next((s for s in probe["streams"]
                            if s["codec_type"] == "audio"), None)
        video_stream = next((s for s in probe["streams"]
                            if s["codec_type"] == "video"), None)

        if not audio_stream or not video_stream:
            return SyncReport(synced=True, offset_ms=0)

        # Comparer les start_pts
        audio_pts = audio_stream.get("start_pts", 0)
        video_pts = video_stream.get("start_pts", 0)
        time_base = float(audio_stream.get("time_base", "1/1000").split("/")[0]) / \
                    float(audio_stream.get("time_base", "1/1000").split("/")[1])

        offset_ms = abs(audio_pts - video_pts) * time_base * 1000
        synced = offset_ms <= LipSyncValidator.THRESHOLD_MS

        return SyncReport(
            synced=synced,
            offset_ms=offset_ms,
            audio_stream_index=audio_stream["index"],
            video_stream_index=video_stream["index"],
        )
```

### 15.6 Autres pièges

| Piège | Symptôme | Solution |
|-------|----------|----------|
| B-roll non trouvé | Trou noir dans la vidéo | Fallback placeholder généré |
| Segment trop court (< 1s) | Flash imperceptible | Fusionner avec le segment suivant ou ignorer |
| Chemins absolus vs relatifs | FFmpeg ne trouve pas les fichiers | Toujours convertir en absolu avant d'appeler FFmpeg |
| Nombre pair de pixels requis | Erreur codec | Forcer `ceil(w/2)*2` sur toutes les résolutions |
| Caractères spéciaux dans les chemins | FFmpeg échoue | `shlex.quote()` sur tous les chemins |
| Sous-titres qui débordent | Texte tronqué | Wrap automatique, max_width_pct |
| Mémoire insuffisante en rendu | OOM kill | `max_concurrent_renders`, segments séquentiels |

---

## 16. Tests

### 16.1 Tests unitaires

```python
# tests/test_templates.py
class TestTemplateEngine:
    def test_resolve_facecam(self):
        config = MontageConfig(facecam_position="bottom-left")
        segment = CutSegment(id="t1", type="facecam", ...)
        template = TemplateEngine.resolve(segment, config)
        assert template.layout["speaker"]["x"] == 0.02
        assert template.layout["speaker"]["y"] == 1 - 0.25 - 0.02

    def test_resolve_split_default(self):
        segment = CutSegment(id="t2", type="split", ...)
        template = TemplateEngine.resolve(segment, MontageConfig())
        assert template.layout["speaker"]["w"] == 0.5
        assert template.layout["broll"]["w"] == 0.5


# tests/test_broll_placer.py
class TestBrollPlacer:
    def test_priority_sorting(self):
        placer = BrollPlacer(MontageConfig())
        suggestions = [
            BrollPlacement(concept="low", priority=2, ...),
            BrollPlacement(concept="high", priority=9, ...),
        ]
        result = placer._filter_valid(suggestions)
        assert result[0].concept == "high"

    def test_overlap_resolution(self):
        placer = BrollPlacer(MontageConfig())
        overlapping = [
            BrollPlacement(concept="a", priority=8, start=0, end=5, placement="fullscreen"),
            BrollPlacement(concept="b", priority=5, start=2, end=7, placement="fullscreen"),
        ]
        resolved = placer._resolve_overlaps(overlapping, mock_segment)
        assert len(resolved) == 1  # Un seul fullscreen gardé


# tests/test_subtitles.py
class TestSubtitleEngine:
    def test_block_generation(self):
        engine = SubtitleEngine(SubtitleConfig(style="block"))
        segment = CutSegment(id="t1", transcript="Hello world", start=0, end=5)
        events = engine._generate_block(segment)
        assert len(events) == 1
        assert events[0].text == "Hello world"

    def test_karaoke_generation(self):
        engine = SubtitleEngine(SubtitleConfig(style="karaoke"))
        segment = CutSegment(id="t1", start=0, end=3)
        words = [{"text": "Hello", "start": 0, "end": 1},
                  {"text": "world", "start": 1, "end": 3}]
        events = engine._generate_karaoke(segment, words)
        assert len(events) == 2
        assert events[0].text == "Hello"


# tests/test_ffmpeg_ops.py
class TestFFmpegOps:
    def test_extract_segment(self):
        # Tester avec un petit fichier de test
        pass

    def test_concat_simple(self):
        # Tester la concaténation sans transition
        pass

    def test_sync_detection(self):
        # Vérifier que le detect_sync_offset fonctionne
        report = LipSyncValidator.validate(test_video)
        assert report.synced == True
```

### 16.2 Tests d'intégration

```python
# tests/integration/test_full_pipeline.py
class TestFullMontagePipeline:
    """Test d'intégration complet avec une vidéo de test."""

    async def test_preview_pipeline(self):
        """Pipeline complet en mode preview."""
        pipeline = MontagePipeline()
        report = await pipeline.run(
            cut_list_path=TEST_DATA / "cut_list.json",
            script_path=TEST_DATA / "script_cleaned.txt",
            source_video=TEST_DATA / "test_source_30s.mp4",
            config=MontageConfig(preview_scale=0.5),
            mode="preview",
        )
        assert report.output_path.exists()
        assert report.total_segments > 0
        assert all(s.render_success for s in report.segments)

    async def test_quality_loop(self):
        """Test de la boucle qualité avec feedback simulé."""
        loop = QualityLoop(config=..., agent5_endpoint="http://mock/")
        video, report = await loop.run_quality_loop(video_path, report)
        # Vérifier que les corrections ont été appliquées
```

---

## Annexes

### A. Dépendances Python

```txt
# requirements.txt
pydantic>=2.7.0
typer>=0.9.0
httpx>=0.27.0
asyncio
# Optionnel : pour analyse vidéo avancée
# opencv-python>=4.9.0
# numpy>=1.26.0
```

### B. Dépendances système

```dockerfile
# Dockerfile.agent3
FROM python:3.11-slim

# FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Node.js pour Remotion/Hyperframes
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Puppeteer (pour Remotion)
RUN npx puppeteer browsers install chrome

WORKDIR /app
COPY src/agent3_montage/ .
RUN pip install -r requirements.txt

# Pour Hyperframes : exposition du port
EXPOSE 3000

ENTRYPOINT ["python", "-m", "agent3_montage.cli"]
```

### C. Exemple de cut_list.json (entrée)

```json
{
  "segments": [
    {
      "id": "seg_001",
      "start_time": 0.0,
      "end_time": 12.5,
      "type": "facecam",
      "transcript": "Bienvenue dans cette vidéo sur l'architecture des microservices.",
      "transition_out": "fade"
    },
    {
      "id": "seg_002",
      "start_time": 12.5,
      "end_time": 25.0,
      "type": "split",
      "transcript": "Comme vous pouvez le voir sur ce diagramme, chaque service est indépendant.",
      "brolls": [
        {
          "concept": "diagramme architecture microservices",
          "placement": "split",
          "priority": 10,
          "start_time": 12.5,
          "end_time": 25.0
        }
      ],
      "transition_out": "cut"
    },
    {
      "id": "seg_003",
      "start_time": 25.0,
      "end_time": 40.0,
      "type": "full_broll",
      "transcript": "Voici un exemple de déploiement Kubernetes en production.",
      "brolls": [
        {
          "concept": "kubernetes dashboard production",
          "placement": "fullscreen",
          "priority": 9,
          "start_time": 25.0,
          "end_time": 40.0
        }
      ],
      "transition_out": "fade"
    }
  ],
  "broll_suggestions": [
    {
      "concept": "kubernetes dashboard production",
      "placement": "fullscreen",
      "priority": 9,
      "start_time": 25.0,
      "end_time": 40.0
    }
  ],
  "metadata": {
    "source_duration": 300.0,
    "total_cut_duration": 40.0,
    "compression_ratio": 0.13
  }
}
```

### D. Exemple de sortie montage_report.json

```json
{
  "pipeline_version": "3.0.0",
  "source_video": "source_video.mp4",
  "total_segments": 3,
  "total_duration": 40.0,
  "segments": [
    {
      "segment_id": "seg_001",
      "source_range": [0.0, 12.5],
      "template_type": "facecam",
      "duration": 12.5,
      "brolls_applied": 0,
      "render_success": true,
      "render_duration_ms": 4520,
      "output_path": "/tmp/agent3_cache/seg_001_rendered.mp4"
    },
    {
      "segment_id": "seg_002",
      "source_range": [12.5, 25.0],
      "template_type": "split",
      "duration": 12.5,
      "brolls_applied": 1,
      "render_success": true,
      "render_duration_ms": 6120,
      "output_path": "/tmp/agent3_cache/seg_002_rendered.mp4"
    }
  ],
  "brolls_total": 2,
  "brolls_placed": 2,
  "transitions_applied": ["fade", "cut"],
  "subtitle_style": "block",
  "render_mode": "final",
  "total_render_time_ms": 28450,
  "output_path": "/output/video_montage_final.mp4",
  "preview_path": "/output/video_montage_preview.mp4",
  "errors": []
}
```

---

> **Document créé le 08/07/2026 — Agent #3 Montage & Animation v3.0.0**
> Dernière mise à jour : 08/07/2026
