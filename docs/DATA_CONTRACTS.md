# Data Contracts — Contrats d'Interface entre Agents

Tous les échanges de données entre agents sont strictement typés via **Pydantic v2.7+**. Les schémas ci-dessous définissent le contrat d'interface pour chaque transition du pipeline.

---

## Table des Contrats

| # | Source → Destination | Schéma | Fichier | Définition Pydantic |
|---|---------------------|--------|---------|---------------------|
| 1 | Agent #1 → Agent #2 | `TranscriptOutput` | `transcript.json` | `docs/agent1_schemas.py` |
| 2 | Agent #2 → Agent #3 | `CutList` + `BRollSuggestions` + `CleanScript` | `cutlist.json` | `agents/agent2_derushage/schemas.py` |
| 3 | Agent #3 → Agent #4 | `EditMetadata` | `edit_metadata.json` | `docs/agent4_schemas.py` → `EditMetadata` |
| 4 | Agent #4 → Agent #5 | `AudioMetadata` | `audio_metadata.json` | `docs/agent4_schemas.py` → `AudioMetadata` |
| 5 | Agent #5 → Agent #6 | `QaReport` | `qa_report.json` | `agents/agent5_quality/schemas.py` |
| 6 | Agent #5 → Boucle | `FeedbackInstructions` | `feedback.json` | `agents/agent5_quality/schemas.py` |
| 7 | Agent #6 → Final | `HumanApproval` | `approval.json` | — |

---

## Contrat #1 : Agent #1 → Agent #2 (Transcription)

**Fichier :** `transcript.json`

```python
# shared/schemas/transcription.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import timedelta
from enum import Enum

class SegmentType(str, Enum):
    speech = "speech"
    silence = "silence"
    music = "music"
    noise = "noise"

class TranscriptSegment(BaseModel):
    """Un segment de transcription — parole, silence, ou autre."""
    text: str = Field(
        ..., description="Texte transcrit (peut être vide pour silences)"
    )
    start: float = Field(
        ..., ge=0.0, description="Timecode début en secondes"
    )
    end: float = Field(
        ..., ge=0.0, description="Timecode fin en secondes"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Score de confiance de la transcription"
    )
    speaker: Optional[str] = Field(
        default=None, description="Identifiant du locuteur si diarization"
    )
    segment_type: SegmentType = Field(
        default=SegmentType.speech,
        description="Type de segment (parole, silence, musique, bruit)"
    )
    source: str = Field(
        ..., description="Source : 'scribe_v2', 'whisperx', 'silence_detector'"
    )
    words: Optional[list[dict]] = Field(
        default=None,
        description="Mots individuels avec timecodes (WhisperX format)"
    )
    errors: Optional[list[str]] = Field(
        default=None,
        description="Erreurs potentielles détectées (filler words, etc.)"
    )

class TranscriptionMetadata(BaseModel):
    """Métadonnées de la transcription."""
    duration: float = Field(..., description="Durée totale vidéo (secondes)")
    language: str = Field(default="fr", description="Langue détectée")
    source_video: str = Field(..., description="Chemin fichier source")
    whisperx_used: bool = Field(default=True)
    scribe_v2_used: bool = Field(default=True)
    silence_threshold_db: float = Field(
        default=-35.0, description="Seuil de détection silence (dB)"
    )
    total_segments: int = Field(..., ge=1)
    speech_segments: int = Field(..., ge=0)
    silence_segments: int = Field(..., ge=0)

class TranscriptOutput(BaseModel):
    """Sortie complète de l'Agent #1."""
    schema_version: str = Field(default="1.0")
    metadata: TranscriptionMetadata
    segments: list[TranscriptSegment] = Field(
        ..., min_length=1,
        description="Tous les segments temporels"
    )
    full_text: str = Field(
        ..., description="Texte brut complet concaténé"
    )
```

**Exemple JSON :**
```json
{
  "schema_version": "1.0",
  "metadata": {
    "duration": 124.53,
    "language": "fr",
    "source_video": "/data/raw/interview_redd.mp4",
    "whisperx_used": true,
    "scribe_v2_used": true,
    "silence_threshold_db": -35.0,
    "total_segments": 47,
    "speech_segments": 32,
    "silence_segments": 15
  },
  "segments": [
    {
      "text": "La vidéo que tu vois à l'écran, je ne l'ai pas montée.",
      "start": 0.0,
      "end": 3.2,
      "confidence": 0.985,
      "speaker": "SPEAKER_00",
      "segment_type": "speech",
      "source": "scribe_v2",
      "words": [
        {"word": "La", "start": 0.0, "end": 0.12},
        {"word": "vidéo", "start": 0.12, "end": 0.45}
      ],
      "errors": null
    },
    {
      "text": "",
      "start": 3.2,
      "end": 4.1,
      "confidence": 1.0,
      "speaker": null,
      "segment_type": "silence",
      "source": "silence_detector",
      "words": null,
      "errors": null
    },
    {
      "text": "J'ai réussi à automatiser 97% du montage vidéo.",
      "start": 4.1,
      "end": 6.8,
      "confidence": 0.962,
      "speaker": "SPEAKER_00",
      "segment_type": "speech",
      "source": "whisperx",
      "words": null,
      "errors": ["hésitation probable avant 'réussi'"]
    }
  ],
  "full_text": "La vidéo que tu vois à l'écran, je ne l'ai pas montée. J'ai réussi à automatiser 97% du montage vidéo."
}
```

---

## Contrat #2 : Agent #2 → Agent #3 (Analyse Narrative & Dérushage)

**Fichier :** `cutlist.json`

```python
# shared/schemas/narrative.py
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class ErrorType(str, Enum):
    filler_word = "filler_word"           # "euh", "bah", "en fait"
    repetition = "repetition"             # mot/phrase répété
    stutter = "stutter"                   # bégaiement
    false_start = "false_start"           # phrase abandonnée
    grammatical_error = "grammatical"     # erreur de grammaire
    factual_error = "factual"             # erreur factuelle
    off_topic = "off_topic"              # hors-sujet
    awkward_pause = "awkward_pause"       # pause gênante
    other = "other"                       # autre

class ErrorDetection(BaseModel):
    """Erreur détectée dans le transcript."""
    error_type: ErrorType
    original_text: str = Field(..., description="Texte original contenant l'erreur")
    corrected_text: Optional[str] = Field(
        default=None, description="Texte corrigé suggéré"
    )
    start: float = Field(..., description="Début en secondes")
    end: float = Field(..., description="Fin en secondes")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confiance de la détection"
    )
    explanation: str = Field(
        ..., description="Justification de la détection"
    )

class KeptSegment(BaseModel):
    """Segment conservé dans le montage final."""
    index: int = Field(..., ge=0)
    start: float = Field(..., description="Timecode début")
    end: float = Field(..., description="Timecode fin")
    text: str = Field(..., description="Texte à garder")
    topic: Optional[str] = Field(default=None, description="Thème du segment")
    sentiment: Optional[str] = Field(
        default=None, description="Sentiment : positive/negative/neutral"
    )
    importance: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Importance narrative (1.0 = essentiel)"
    )
    suggested_transition_in: Optional[str] = Field(
        default="cut",
        description="Transition d'entrée suggérée"
    )
    suggested_transition_out: Optional[str] = Field(
        default="cut",
        description="Transition de sortie suggérée"
    )

class RemovedSegment(BaseModel):
    """Segment supprimé du montage."""
    index: int
    start: float
    end: float
    text: str
    reason: str = Field(..., description="Raison de la suppression")
    error_types: list[ErrorType] = Field(default_factory=list)

class BRollType(str, Enum):
    stock_footage = "stock_footage"
    screen_recording = "screen_recording"
    animated_graphic = "animated_graphic"
    photo = "photo"
    text_overlay = "text_overlay"
    split_screen = "split_screen"

class BRollSuggestion(BaseModel):
    """Suggestion de B-roll pour un segment."""
    segment_index: int = Field(..., description="Index du segment KeptSegment cible")
    time_start: float = Field(..., description="Début du B-roll dans la timeline")
    duration: float = Field(..., description="Durée du B-roll en secondes")
    type: BRollType
    description: str = Field(
        ..., description="Description visuelle de ce qu'il faut montrer"
    )
    search_query: Optional[str] = Field(
        default=None,
        description="Requête pour recherche de footage"
    )
    priority: int = Field(
        default=1, ge=1, le=5,
        description="Priorité (1 = essentiel, 5 = optionnel)"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Mots-clés pour la recherche"
    )

class CutList(BaseModel):
    """Plan de montage complet — sortie principale de l'Agent #2."""
    schema_version: str = Field(default="1.0")
    source_transcript: str = Field(..., description="Chemin fichier transcript source")

    # Analyse
    errors_detected: list[ErrorDetection] = Field(
        default_factory=list, description="Toutes les erreurs détectées"
    )
    
    # Décisions de montage
    kept_segments: list[KeptSegment] = Field(
        ..., min_length=1, description="Segments à garder dans le montage"
    )
    removed_segments: list[RemovedSegment] = Field(
        default_factory=list, description="Segments supprimés"
    )
    
    # Métriques
    compression_ratio: float = Field(
        ..., ge=0.0, le=1.0,
        description="Ratio durée gardée / durée totale"
    )
    original_duration: float = Field(..., description="Durée originale (secondes)")
    final_duration: float = Field(..., description="Durée après dérushage (secondes)")

    # Options de montage supplémentaires
    preferred_pace: str = Field(
        default="dynamic", description="Rythme : 'dynamic', 'calm', 'fast'"
    )
    tone: str = Field(
        default="professional",
        description="Ton : 'professional', 'casual', 'educational', 'inspirational'"
    )
    visual_style: Optional[str] = Field(
        default=None, description="Style visuel suggéré"
    )

class CleanScript(BaseModel):
    """Script nettoyé — version lissée du transcript."""
    schema_version: str = Field(default="1.0")
    original_full_text: str
    cleaned_full_text: str = Field(
        ..., description="Texte sans erreurs, fluide et lisible"
    )
    segments: list[KeptSegment] = Field(
        ..., description="Segments dans l'ordre, version nettoyée"
    )

class BRollSuggestions(BaseModel):
    """Ensemble des suggestions de B-roll."""
    schema_version: str = Field(default="1.0")
    suggestions: list[BRollSuggestion]
    total_suggestions: int
    music_mood: Optional[str] = Field(
        default=None, description="Ambiance musicale suggérée"
    )
    color_palette: Optional[list[str]] = Field(
        default=None, description="Palette de couleurs suggérée"
    )
```

**Exemple JSON :**
```json
{
  "schema_version": "1.0",
  "source_transcript": "/data/transcriptions/transcript_interview.json",
  "errors_detected": [
    {
      "error_type": "filler_word",
      "original_text": "bah en fait le truc c'est que",
      "corrected_text": "Le fait est que",
      "start": 15.2,
      "end": 17.8,
      "confidence": 0.94,
      "explanation": "Tic de langage 'bah en fait' — suppression recommandée"
    }
  ],
  "kept_segments": [
    {
      "index": 0,
      "start": 0.0,
      "end": 3.2,
      "text": "La vidéo que tu vois à l'écran, je ne l'ai pas montée.",
      "topic": "accroche",
      "sentiment": "neutral",
      "importance": 1.0,
      "suggested_transition_in": "fade_in",
      "suggested_transition_out": "cut"
    }
  ],
  "removed_segments": [],
  "compression_ratio": 0.76,
  "original_duration": 124.53,
  "final_duration": 94.64,
  "preferred_pace": "dynamic",
  "tone": "educational",
  "visual_style": "modern_minimal"
}
```

---

## Contrat #3 : Agent #3 → Agent #4 (Montage → Audio)

**Fichier :** `edit_metadata.json`
**Définition Pydantic :** `docs/agent4_schemas.py` → `EditMetadata`

```python
# docs/agent4_schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class EditSegmentTiming(BaseModel):
    """Timing d'un segment dans le montage final."""
    montage_start: float = Field(..., description="Début dans le montage final (s)")
    montage_end: float = Field(..., description="Fin dans le montage final (s)")
    original_start: float = Field(..., description="Début dans la vidéo brute (s)")
    original_end: float = Field(..., description="Fin dans la vidéo brute (s)")
    text: str = Field(..., description="Texte du segment")

class EditMetadata(BaseModel):
    """Métadonnées de la version montée — entrée Agent #4."""
    schema_version: str = Field(default="1.0")
    source_cutlist: str = Field(..., description="Chemin fichier cutlist source")
    total_duration: float = Field(..., description="Durée totale du montage (s)")
    
    segments: list[EditSegmentTiming] = Field(..., description="Timing de chaque segment dans le montage")
    pace: str = Field(..., description="'slow', 'medium', 'fast'")
    beat_per_minute_estimate: Optional[float] = Field(default=None)
    
    scene_changes: list[float] = Field(default_factory=list, description="Timecodes changements scène (s)")
    dominant_colors: Optional[list[str]] = Field(default=None)
    mood: Optional[str] = Field(default=None, description="'energetic', 'calm', 'dramatic', 'professional'")
    speech_segments: list[dict] = Field(default_factory=list, description="[{start, end, text}] pour ducking parole/musique")
```

---

## Contrat #4 : Agent #4 → Agent #5 (Audio → Qualité)

**Fichier :** `audio_metadata.json`
**Définition Pydantic :** `docs/agent4_schemas.py` → `AudioMetadata`

```python
# docs/agent4_schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class AudioTrack(BaseModel):
    """Piste audio utilisée dans le montage."""
    type: str = Field(..., description="'music', 'sfx', 'voice', 'ambiance'")
    source: str = Field(..., description="Source : 'epidemic_sound', 'generated', 'original'")
    track_id: Optional[str] = Field(default=None, description="ID Epidemic Sound")
    title: Optional[str] = Field(default=None, description="Titre du morceau")
    start: float = Field(..., description="Début dans le montage (s)")
    end: float = Field(..., description="Fin dans le montage (s)")
    volume_db: float = Field(default=0.0, description="Volume relatif (dB)")
    ducking_applied: bool = Field(default=False)

class AudioMetadata(BaseModel):
    """Métadonnées de la piste audio finale."""
    schema_version: str = Field(default="1.0")
    source_edit: str = Field(..., description="Chemin montage source")
    
    tracks: list[AudioTrack] = Field(..., description="Toutes les pistes audio")
    master_volume_db: float = Field(default=0.0, description="Volume master (dB)")
    peak_level_db: float = Field(..., description="Pic de niveau (dB)")
    rms_level_db: float = Field(..., description="Niveau RMS moyen (dB)")
    loudness_lufs: float = Field(..., description="Loudness intégré (LUFS)")
    
    music_epidemic_id: Optional[str] = Field(default=None)
    music_bpm: Optional[float] = Field(default=None)
    music_key: Optional[str] = Field(default=None)
    
    sfx_count: int = Field(default=0, description="Nombre d'effets sonores")
```

---

## Contrat #5 : Agent #5 → Agent #6 (Qualité → Orchestrator)

**Fichier :** `qa_report.json`

```python
# shared/schemas/qa.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class ScoreCategory(str, Enum):
    narrative_coherence = "narrative_coherence"
    audio_quality = "audio_quality"
    visual_quality = "visual_quality"
    pacing = "pacing"
    motion_design = "motion_design"
    subtitle_accuracy = "subtitle_accuracy"
    overall = "overall"

class MetricScore(BaseModel):
    """Score d'une métrique qualité."""
    category: ScoreCategory
    score: float = Field(..., ge=0.0, le=1.0, description="Score normalisé 0-1")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Poids dans le score global")
    details: str = Field(default="", description="Commentaire détaillé")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions d'amélioration")

class IterationInfo(BaseModel):
    """Information sur l'itération actuelle."""
    iteration_number: int = Field(..., ge=1, le=3)
    previous_scores: Optional[dict[str, float]] = Field(default=None)
    improvements_made: list[str] = Field(default_factory=list)

class QaReport(BaseModel):
    """Rapport complet de qualité."""
    schema_version: str = Field(default="1.0")
    source_video: str = Field(..., description="Chemin vidéo analysée")
    source_cutlist: str = Field(..., description="Chemin cutlist associée")
    
    timestamp: datetime = Field(default_factory=datetime.now)
    iteration: IterationInfo
    
    # Scores
    metrics: list[MetricScore] = Field(..., min_length=1)
    overall_score: float = Field(..., ge=0.0, le=1.0)
    passed: bool = Field(..., description="True si score >= threshold")
    threshold: float = Field(default=0.7, description="Seuil de passage")
    
    # Feedback
    summary: str = Field(..., description="Résumé exécutif de l'analyse")
    critical_issues: list[str] = Field(default_factory=list, description="Problèmes bloquants")
    improvement_feedback: Optional[str] = Field(
        default=None,
        description="Feedback structuré pour Claude/Codex"
    )
    
    # Décision
    decision: str = Field(
        ..., description="'approved', 'needs_improvement', 'rejected'"
    )
    next_action: Optional[str] = Field(
        default=None,
        description="Prochaine action : 'iterate_editing', 'iterate_audio', 'human_review', 'complete'"
    )

class FeedbackInstructions(BaseModel):
    """Instructions de feedback pour la boucle d'auto-amélioration."""
    schema_version: str = Field(default="1.0")
    target_agent: str = Field(
        ..., description="Agent cible : 'editing', 'audio', 'narrative'"
    )
    issues: list[dict] = Field(..., description="Problèmes à corriger")
    suggested_changes: str = Field(
        ..., description="Instructions détaillées pour l'agent cible"
    )
    priority: str = Field(default="high", description="'high', 'medium', 'low'")
```

---

## Contrat #6 : Agent #6 → Final (Validation Humaine)

**Fichier :** `approval.json`

```python
# shared/schemas/approval.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class HumanApproval(BaseModel):
    """Approbation humaine finale obligatoire."""
    schema_version: str = Field(default="1.0")
    pipeline_run_id: str = Field(..., description="ID unique de l'exécution")
    video_path: str = Field(..., description="Chemin vidéo finale")
    
    # Décision
    approved: bool
    reviewer_name: str = Field(..., description="Nom du validateur humain")
    reviewed_at: datetime = Field(default_factory=datetime.now)
    
    # Commentaires
    comments: Optional[str] = Field(
        default=None, description="Commentaires du validateur"
    )
    requested_changes: Optional[list[str]] = Field(
        default=None, description="Modifications demandées"
    )
    
    # Redo
    requires_redo: bool = Field(default=False)
    redo_agent: Optional[str] = Field(
        default=None,
        description="Agent à relancer si redo"
    )
    redo_feedback: Optional[str] = Field(
        default=None, description="Instructions pour le redo"
    )
    
    # Artefacts
    artefact_paths: list[str] = Field(
        default_factory=list,
        description="Chemins de tous les artefacts produits"
    )
    video_final_path: str = Field(
        ..., description="Chemin final de la vidéo livrée"
    )
```

---

## Contrat Machine d'État (Orchestrator Interne)

```python
# agents/agent-6-orchestrator/src/state_machine.py
from enum import Enum

class PipelineState(str, Enum):
    idle = "idle"
    new_job = "new_job"
    transcribing = "transcribing"
    transcribing_done = "transcribing_done"
    analyzing = "analyzing"
    analyzing_done = "analyzing_done"
    editing = "editing"
    editing_done = "editing_done"
    mixing = "mixing"
    mixing_done = "mixing_done"
    qa_check = "qa_check"
    qa_passed = "qa_passed"
    qa_failed = "qa_failed"
    iterating = "iterating"
    human_review = "human_review"
    human_approved = "human_approved"
    human_rejected = "human_rejected"
    completed = "completed"
    failed = "failed"

class PipelineEvent(str, Enum):
    start_job = "start_job"
    transcription_complete = "transcription_complete"
    analysis_complete = "analysis_complete"
    editing_complete = "editing_complete"
    mixing_complete = "mixing_complete"
    qa_complete_pass = "qa_complete_pass"
    qa_complete_fail = "qa_complete_fail"
    max_iterations = "max_iterations"
    human_approve = "human_approve"
    human_reject = "human_reject"
    error = "error"
```

---

## Validation & Sérialisation

Tous les contrats utilisent Pydantic v2.7+ :

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Any

def validate_contract(data: dict, schema: type[BaseModel]) -> BaseModel:
    """Valide et parse une entrée selon le schéma."""
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        raise ContractValidationError(
            f"Validation échouée pour {schema.__name__}: {e}"
        )

def serialize_contract(instance: BaseModel) -> dict[str, Any]:
    """Sérialise une instance en dict JSON-compatible."""
    return instance.model_dump(mode="json", by_alias=True)

def load_contract(path: str, schema: type[BaseModel]) -> BaseModel:
    """Charge et valide un fichier JSON."""
    import json
    with open(path, "r") as f:
        data = json.load(f)
    return validate_contract(data, schema)

def save_contract(instance: BaseModel, path: str) -> None:
    """Sauvegarde une instance en JSON."""
    import json
    with open(path, "w") as f:
        json.dump(
            instance.model_dump(mode="json", by_alias=True),
            f,
            indent=2,
            ensure_ascii=False
        )
```

---

## Résumé des Flux

```
Agent #1                         Agent #2
  ┌──────────────────┐            ┌──────────────────────┐
  │ TranscriptOutput │   ────▶   │ CutList              │
  │ (transcript.json)│            │ CleanScript          │
  └──────────────────┘            │ BRollSuggestions     │
                                  └──────────┬───────────┘
                                             │
Agent #3                          Agent #4    ▼
  ┌──────────────────┐            ┌──────────────────────┐
  │ EditMetadata     │   ────▶   │ AudioMetadata        │
  │ (edit_metadata)  │            │ (audio_metadata.json)│
  └──────────────────┘            └──────────┬───────────┘
                                             │
Agent #5                          Agent #6    ▼
  ┌──────────────────┐            ┌──────────────────────┐
  │ QaReport         │   ────▶   │ HumanApproval        │
  │ FeedbackInstr.   │            │ (approval.json)      │
  └──────────────────┘            └──────────────────────┘
```
