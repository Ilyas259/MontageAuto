# Agent #2 — Analyse Narrative & Dérushage

> **Module** : Narrative Analyzer  
> **Version** : 1.0.0  
> **Auteur** : Redd  
> **Pipeline** : Montage vidéo automatisé  
> **Entrée** : `transcript.json` (Agent #1)  
> **Sortie** : `cut_list.json` + `script_cleaned.txt` (→ Agent #3)

---

## Table des matières

1. [Mission & Vision](#1-mission--vision)
2. [Architecture du module](#2-architecture-du-module)
3. [Étape 1 — Préparation du Transcript](#3-étape-1--préparation-du-transcript)
4. [Étape 2 — Analyse Sémantique LLM](#4-étape-2--analyse-sémantique-llm)
5. [Étape 3 — Logique de Dérushage (Cut Engine)](#5-étape-3--logique-de-dérushage-cut-engine)
6. [Étape 4 — Suggestion de B-Rolls](#6-étape-4--suggestion-de-b-rolls)
7. [Étape 5 — Script Nettoyé](#7-étape-5--script-nettoyé)
8. [Schémas Pydantic](#8-schémas-pydantic)
9. [Interface CLI & Docker](#9-interface-cli--docker)
10. [Configuration externalisée](#10-configuration-externalisée)
11. [Tests](#11-tests)
12. [Pièges connus](#12-pièges-connus)

---

## 1. Mission & Vision

### Mission

L'Agent #2 est le cerveau du dérushage. Il lit le `transcript.json` produit par l'Agent #1 (mots, timestamps, silences, speakers) et produit :

1. **`cut_list.json`** : La liste exacte des segments vidéo à conserver, avec timecodes précis, type de cut, et justification
2. **`script_cleaned.txt`** : Le texte final de la vidéo, nettoyé de toutes les hésitations, bégaiements et fausses pistes

### Vision (extrait vidéo source)

> *"Le dérushage, c'est le truc qui fonctionne de manière assez aléatoire mais quand même, ça va toucher les 80-90% au niveau de la perfection. C'est juste qu'il va falloir calibrer selon votre style de montage, sur à quel point vous voulez être agressif avec le fait de retirer les silences."*

### Principe fondamental

Le dérushage n'est **pas** juste "supprimer les silences". C'est une **opération sémantique** : le LLM comprend le sens pour distinguer :

| Type de pause / erreur | Action |
|------------------------|--------|
| Pause dramatique **intentionnelle** | À **garder** |
| Silence technique **mort** | À **couper** |
| Répétition expressive (rythme oratoire) | À **garder** |
| Bégaiement / correction | À **couper** |
| Fausse piste (phrase abandonnée) | À **couper** |
| Reformulation utile (mieux dit) | Garder la **meilleure version** |

---

## 2. Architecture du Module

### Structure des fichiers

```
narrative_analyzer/
├── Dockerfile
├── requirements.txt
├── config.yaml                     # Paramètres de dérushage externalisés
├── README.md
├── prompts/
│   ├── system_analyzer.j2          # Prompt système — analyse sémantique
│   ├── system_narrative.j2         # Prompt système — structuration narrative
│   └── user_transcript.j2          # Template d'injection du transcript
├── src/
│   ├── __init__.py
│   ├── main.py                     # CLI orchestrateur
│   ├── transcript_processor.py     # Prétraitement & segmentation
│   ├── semantic_analyzer.py        # Appel LLM (OpenRouter) pour analyse
│   ├── cut_engine.py               # Logique temporelle de découpage
│   ├── b_roll_suggester.py         # Suggestion de B-rolls par concept
│   ├── script_cleaner.py           # Génération du script nettoyé
│   └── llm_client.py               # Client OpenRouter avec retry/fallback
├── schemas/
│   ├── __init__.py
│   ├── cut_list_schema.py          # Modèles Pydantic cut_list
│   └── analysis_schema.py          # Modèles pour la réponse LLM
└── tests/
    ├── __init__.py
    ├── test_analyzer.py
    └── fixtures/
        └── sample_transcript.json  # Transcript factice pour les tests
```

### Data Flow interne

```
transcript.json
      │
      ▼
┌─────────────────────────┐
│ Étape 1: Transcript     │ ← Segmentation logique, patterns de ratés
│ Processor               │
└─────────┬───────────────┘
          │ transcript préparé
          ▼
┌─────────────────────────┐
│ Étape 2: Semantic       │ ← Appel OpenRouter (Qwen2.5-72B)
│ Analyzer (LLM)          │ → Détection: false_start, stutter, filler,
└─────────┬───────────────┘   dead_pause, repetition
          │ liste d'erreurs
          ▼
┌─────────────────────────┐
│ Étape 3: Cut Engine     │ ← Calcul physique des cuts (PAS le LLM)
│ (code Python)           │ → Fusion, padding, inversion, filtrage
└─────────┬───────────────┘
          │ kept_segments + removed_segments
          ▼
┌─────────────────────────┐
│ Étape 4: B-Roll         │ ← Analyse sémantique des concepts visuels
│ Suggester               │ → Suggestions avec timestamp, durée, priorité
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ Étape 5: Script         │ ← Fusion des segments gardés + nettoyage
│ Cleaner                 │ → Suppression fillers + ponctuation
└─────────┬───────────────┘
          │
          ▼
   cut_list.json + script_cleaned.txt → Agent #3
```

---

## 3. Étape 1 — Préparation du Transcript

### Entrée

`/input/transcript.json` — produit par Agent #1.

### Prétraitement

1. **Segmentation en phrases logiques** (pas juste les segments WhisperX) :
   - Regroupement par ponctuation forte (points, points d'interrogation)
   - Regroupement par changement de sujet (détecté par embedding de similarité)
   - Fusion des segments trop courts (< 3 mots) avec le segment suivant

2. **Identification des patterns de ratés** (règles heuristiques) :

```python
PATTERNS = {
    "false_start": [
        r"^[Dd]onc euh[.,!?]?\s+[Dd]onc",     # "Donc euh... donc"
        r"^[Ee]t euh[.,!?]?\s+[Ee]t",         # "Et euh... et"
        r"^[Mm]ais euh[.,!?]?\s+[Mm]ais",     # "Mais euh... mais"
        r"^[Jj]e veux dire[.,!?]?\s+[Jj]e",   # "Je veux dire... je"
    ],
    "stutter": [
        r"\b(\w{1,4})-\1\b",                   # "je-je", "c'-c'"
        r"\b(\w{1,3})-(\w{1,3})-\1\b",         # "je-je-je"
    ],
    "filler": [
        r"\beuh\b", r"\bbah\b", r"\bben\b",
        r"\btu vois\b", r"\ben fait\b",
        r"\bdu coup\b", r"\ben mode\b",
    ],
    "long_pause": [],  # Défini par le silence detector
    "repetition": [],  # Détecté par similarité de phrases adjacentes
}
```

3. **Détection des silences** :
   - Silence > 1.5s au milieu d'une phrase → marqué comme `dead_pause`
   - Silence après ponctuation → `natural_pause` (à garder si `keep_natural_pauses=true`)
   - Silence < 0.3s → ignoré (bruit de bouche, respiration)

### Sortie d'étape

Transcript structuré avec segments enrichis :
```json
{
  "segments": [
    {
      "text": "Donc euh aujourd'hui on va parler",
      "start": 0.0, "end": 2.5,
      "patterns_detected": ["false_start", "filler"],
      "is_punctuation_end": false,
      "has_silence_after": true, "silence_duration": 2.1
    },
    {
      "text": "de l'automatisation.",
      "start": 4.6, "end": 6.2,
      "patterns_detected": [],
      "is_punctuation_end": true,
      "has_silence_after": false
    }
  ],
  "metadata": {
    "source_duration": 120.5,
    "total_silence": 8.3,
    "average_speech_rate": 2.4
  }
}
```

---

## 4. Étape 2 — Analyse Sémantique LLM

### Appel LLM

Le transcript préparé est envoyé à **OpenRouter** avec le prompt système suivant :

```jinja
{# prompts/system_analyzer.j2 #}
Tu es un monteur vidéo senior spécialisé dans le dérushage de contenu YouTube/TikTok.
Tu analyses des transcripts avec timestamps pour identifier les erreurs de parole.

RÈGLES STRICTES :
1. Une "fausse piste" (false_start) est une phrase commencée puis immédiatement 
   abandonnée et recommencée différemment.
2. Un "bégaiement" (stutter) est une répétition de 1-2 mots au début d'un mot.
3. Un "filler" est un mot de remplissage qui n'apporte aucun sens 
   ("euh", "bah", "tu vois").
4. Une "pause morte" (dead_pause) est un silence > 1.5s au milieu d'une phrase 
   sans ponctuation.
5. Une "répétition" (repetition) est la même phrase dite 2 fois de suite.

Pour chaque erreur détectée, retourne :
- type : false_start | stutter | filler | dead_pause | repetition
- start_timestamp : début en secondes
- end_timestamp : fin en secondes  
- confidence : 0.0 à 1.0
- reason : explication courte en français

Retourne UNIQUEMENT un JSON valide. Pas de markdown, pas de texte avant/après.
```

### Modèles LLM

| Priorité | Modèle | Provider | Justification |
|----------|--------|----------|---------------|
| 1 (principal) | `qwen/qwen-2.5-72b-instruct` | OpenRouter | Excellent en français, raisonnement structuré, coût faible |
| 2 (fallback) | `deepseek/deepseek-chat-v3` | OpenRouter | Si Qwen timeout |
| 3 (fallback local) | `Qwen/Qwen2.5-72B-Instruct` | vLLM local | Si OpenRouter indisponible |

### Paramètres d'appel

| Paramètre | Valeur | Justification |
|-----------|--------|---------------|
| Timeout | 60s par appel | Les modèles 72B sont rapides sur OpenRouter |
| Retry | 2x backoff exponentiel (1s, 4s) | Réseau instable |
| Temperature | 0.1 | On veut de la précision, pas de créativité |
| Max tokens | 4096 | Suffisant pour un transcript de 15 min |

### Contrôle de qualité LLM

**Validation des timestamps** : Le LLM peut halluciner des timestamps. Règle de validation :
- Si `start_timestamp` ou `end_timestamp` est hors des bornes du transcript → rechercher le mot le plus proche dans le segment correspondant
- Si aucun mot proche trouvé → rejeter l'erreur avec un log warning
- Si `confidence` < 0.4 → marquer comme "à vérifier" (low confidence)

---

## 5. Étape 3 — Logique de Dérushage (Cut Engine)

> **Principe crucial** : Le LLM identifie les erreurs **sémantiquement**, mais c'est le code Python qui calcule les cuts **physiques** sur la timeline. On ne laisse pas le LLM faire les maths sur les timestamps.

### Algorithme de découpage

```python
def compute_cuts(transcript: Transcript, errors: List[Error],
                 config: DerushConfig) -> CutList:
    """
    Calcule la liste des segments à garder/supprimer.
    
    1. Marquer les zones à supprimer selon les erreurs détectées
    2. Fusionner les zones qui se chevauchent
    3. Appliquer le padding (marges avant/après cut)
    4. Inverser pour obtenir les zones À GARDER
    5. Filtrer les segments trop courts
    """
    # 1. Marquer les zones à supprimer
    remove_zones = []
    
    for error in errors:
        if error.type == "filler" and not config.keep_hesitations:
            remove_zones.append((error.start, error.end, "filler"))
        elif error.type == "dead_pause" and error.duration > config.max_silence_cut:
            remove_zones.append((error.start, error.end, "dead_pause"))
        elif error.type == "false_start":
            remove_zones.append((error.start, error.end, "false_start"))
        elif error.type == "repetition":
            remove_zones.append((error.start, error.end, "repetition"))
        elif error.type == "stutter":
            remove_zones.append((error.start, error.end, "stutter"))
    
    # 2. Fusionner les zones qui se chevauchent
    merged_zones = merge_overlapping(remove_zones)
    
    # 3. Appliquer le padding (évite les cuts trop serrés)
    padded_zones = [
        (
            max(0, s - config.padding_before_cut),
            min(transcript.duration, e + config.padding_after_cut),
            t
        )
        for s, e, t in merged_zones
    ]
    
    # 4. Inverser pour obtenir les zones À GARDER
    kept_segments = invert_zones(padded_zones, transcript.duration)
    
    # 5. Filtrer les segments trop courts
    kept_segments = [
        s for s in kept_segments
        if s.duration >= config.min_segment_duration
    ]
    
    return CutList(segments=kept_segments)
```

### Règles de sagesse additionnelles

1. **False start + silence** : Si une false_start est suivie d'un silence < 0.3s, inclure le silence dans la zone à supprimer (évite les micro-cuts parasites)
2. **Répétition avec meilleure version** : Si une repetition a une version plus fluide (meilleur score de confiance Whisper), garder la meilleure version
3. **Frontière mot** : Ne jamais couper au milieu d'un mot — ajuster sur la frontière mot la plus proche en utilisant les timestamps word-level
4. **Pause comique** : Si une pause > 1.5s est précédée d'une punchline (détectée par LLM contextuel), la garder malgré la durée

### Fonctions auxiliaires

```python
def merge_overlapping(zones: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
    """Fusionne les zones qui se chevauchent ou sont adjacentes (< 0.1s d'écart)."""
    if not zones:
        return []
    sorted_zones = sorted(zones, key=lambda z: z[0])
    merged = [sorted_zones[0]]
    for s, e, t in sorted_zones[1:]:
        prev_s, prev_e, prev_t = merged[-1]
        if s <= prev_e + 0.1:
            # Fusion : garder le type du plus long
            merged[-1] = (prev_s, max(prev_e, e),
                          t if (e - s) > (prev_e - prev_s) else prev_t)
        else:
            merged.append((s, e, t))
    return merged

def invert_zones(remove_zones: List[Tuple[float, float, str]],
                 duration: float) -> List[KeptSegment]:
    """Inverse les zones à supprimer → zones à garder."""
    keep = []
    cursor = 0.0
    for s, e, _ in remove_zones:
        if s > cursor + 0.1:  # Zone à garder
            keep.append(KeptSegment(start=cursor, end=s))
        cursor = e
    if cursor < duration:
        keep.append(KeptSegment(start=cursor, end=duration))
    return keep
```

---

## 6. Étape 4 — Suggestion de B-Rolls

### Mission

Identifier les moments où un B-roll visuel améliorerait la compréhension ou le rythme de la vidéo.

### Algorithme hybride

**Phase 1 — Analyse sémantique par LLM** : Le LLM lit le script nettoyé et identifie les concepts visuels :

| Texte original | Concept visuel suggéré |
|----------------|----------------------|
| "j'ouvre mon ordinateur" | `écran d'ordinateur` |
| "on va dans les réglages" | `interface logiciel` |
| "j'ai filmé ça hier" | `extrait vidéo archivé` |
| "le graphique montre que" | `graphique / data viz` |
| "en 2019, le marché était" | `frise chronologique` |

**Phase 2 — Scoring de placement** :

| Critère | Score | Exemple |
|---------|-------|---------|
| Speaker décrit action concrète sans montrer | **Haut** (1.0) | "je clique sur le bouton paramètres" |
| Transition entre deux sujets | **Moyen** (0.6) | "Maintenant, passons au design" |
| Explication abstraite difficile à illustrer | **Bas** (0.2) | "La philosophie derrière cette approche" |

**Phase 3 — Durée suggérée** : 3-5 secondes par défaut, ajustable selon la densité d'information.

### Règles de limitation

- **Max 1 B-roll toutes les 30-50s** (évite la saturation visuelle)
- **Paramètre ajustable** dans config.yaml
- **Ne pas placer de B-roll pendant une punchline** (risque de distraire)
- **Éviter les concepts redondants** (déduplication par similarité sémantique)

### Format de sortie

```json
{
  "b_roll_suggestions": [
    {
      "timestamp": 45.2,
      "duration": 4.0,
      "concept": "interface graphique logiciel",
      "placement": "split",    // overlay | fullscreen | split
      "priority": "high",
      "reason": "Le speaker décrit un réglage sans le montrer"
    }
  ]
}
```

---

## 7. Étape 5 — Script Nettoyé

### Entrée

Segments conservés (KeptSegments) + texte original

### Règles de nettoyage

1. **Supprimer les fillers** : "euh", "bah", "tu vois", "en fait" (quand redondant)
2. **Supprimer les répétitions** : ne garder que la version la plus fluide
3. **Fusionner les segments** : regrouper les segments coupés en paragraphes logiques
4. **Ajouter de la ponctuation** : le LLM peut reformuler légèrement pour la fluidité, mais **ne pas changer le sens**
5. **Conserver le style oral** : pas de transformation en dissertation écrite

### Exemple

**ORIGINAL** (transcript brut) :
> "Donc euh... donc aujourd'hui on va parler de... de l'automatisation. Euh. L'automatisation c'est- c'est vraiment quelque chose qui... qui change tout."

**NETTOYÉ** :
> "Donc aujourd'hui on va parler de l'automatisation. L'automatisation, c'est vraiment quelque chose qui change tout."

### Format de sortie

```txt
/output/script_cleaned.txt
```

Texte brut, UTF-8, avec paragraphes séparés par des lignes vides.

---

## 8. Schémas Pydantic

```python
# schemas/cut_list_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from decimal import Decimal

class ErrorDetection(BaseModel):
    """Une erreur de parole détectée par le LLM."""
    type: Literal["false_start", "stutter", "filler",
                  "dead_pause", "repetition"]
    start_timestamp: Decimal = Field(..., ge=0)
    end_timestamp: Decimal = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., max_length=200)

class KeptSegment(BaseModel):
    """Segment vidéo à conserver dans le montage final."""
    start: Decimal = Field(..., ge=0)
    end: Decimal = Field(..., ge=0)
    duration: Decimal
    text: str
    speaker: Optional[str] = None
    type: Literal["keep"] = "keep"
    confidence: float = Field(..., ge=0.0, le=1.0)

class RemovedSegment(BaseModel):
    """Segment vidéo à supprimer du montage final."""
    start: Decimal
    end: Decimal
    duration: Decimal
    type: Literal["false_start", "stutter", "filler",
                  "dead_pause", "repetition", "silence"]
    reason: str

class BRollSuggestion(BaseModel):
    """Suggestion de B-roll à un moment précis."""
    timestamp: Decimal
    duration: Decimal = Field(..., ge=1.0, le=10.0)
    concept: str = Field(..., max_length=100)
    placement: Literal["overlay", "fullscreen", "split"] = "overlay"
    priority: Literal["low", "medium", "high"] = "medium"
    reason: str

class CutList(BaseModel):
    """Structure complète de la liste de montage."""
    version: str = "1.0.0"
    source_duration: Decimal
    kept_segments: List[KeptSegment]
    removed_segments: List[RemovedSegment]
    b_roll_suggestions: List[BRollSuggestion]
    total_kept_duration: Decimal
    total_removed_duration: Decimal
    compression_ratio: float = Field(..., ge=0.0, le=1.0)
    subtitle_style: Literal["karaoke", "block", "none"] = "block"
    subtitle_custom: Optional[dict] = None
```

---

## 9. Interface CLI & Docker

### Usage CLI

```bash
# Via Docker
docker run \
  -v /chemin/video/input:/input \
  -v /chemin/video/output:/output \
  -v /chemin/config:/config \
  -e OPENROUTER_API_KEY=sk-or-xxx \
  narrative-agent \
  --input /input/transcript.json \
  --output /output/cut_list.json \
  --script /output/script_cleaned.txt \
  --config /config/derush.yaml

# Via Python directement (dev)
python -m narrative_analyzer \
  --input /input/transcript.json \
  --output /output/cut_list.json \
  --script /output/script_cleaned.txt \
  --config config.yaml \
  --verbose
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["python", "-m", "narrative_analyzer"]
```

### Docker Compose (extrait)

```yaml
services:
  agent2-narrative:
    build: ./narrative_analyzer
    volumes:
      - ./data/transcriptions:/input
      - ./data/cutlists:/output
      - ./config:/config
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    command: >
      --input /input/transcript.json
      --output /output/cut_list.json
      --script /output/script_cleaned.txt
      --config /config/derush.yaml
```

---

## 10. Configuration externalisée

```yaml
# config.yaml
narrative:
  # Agressivité du dérushage
  aggressiveness: "medium"     # low | medium | high
  
  # Paramètres silences
  min_silence_keep: 0.3        # secondes — en dessous, on garde
  max_silence_cut: 2.0         # secondes — au-dessus, on coupe d'office
  
  # Comportement
  keep_hesitations: false       # Garder les "euh" et "bah" ?
  keep_natural_pauses: true     # Garder les pauses après ponctuation ?
  
  # Marges de cut
  padding_before_cut: 0.15      # marge avant cut (sécurité)
  padding_after_cut: 0.15       # marge après cut
  min_segment_duration: 1.0     # segment minimum conservé

  # B-rolls
  broll:
    max_per_minute: 2           # Max 2 B-rolls par minute
    min_interval: 30            # secondes minimum entre deux B-rolls
    default_duration: 4.0       # Durée par défaut (secondes)

  # LLM
  llm:
    provider: "openrouter"
    model: "qwen/qwen-2.5-72b-instruct"
    fallback: "deepseek/deepseek-chat-v3"
    local_fallback: "qwen-72b"  # via vLLM
    timeout: 60
    max_retries: 2
  
  # Logging
  log_level: "INFO"
  warn_if_compression_below: 0.5  # Warning si < 50% gardé
```

### Profil agressif vs naturel

| Paramètre | Agressif | Naturel |
|-----------|----------|---------|
| `aggressiveness` | `high` | `low` |
| `max_silence_cut` | `0.8s` | `2.5s` |
| `keep_hesitations` | `false` | `true` |
| `keep_natural_pauses` | `false` | `true` |
| `min_segment_duration` | `0.5s` | `1.5s` |
| `padding_before/after_cut` | `0.05s` | `0.3s` |

---

## 11. Tests

### Test 1 — Transcript factice avec fausses pistes connues

```python
def test_false_start_detection():
    """Vérifie que les false_starts sont correctement détectées."""
    transcript = TranscriptFixture.with_false_starts()
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(transcript)
    
    false_starts = [e for e in errors if e.type == "false_start"]
    assert len(false_starts) >= 1
    assert all(e.confidence > 0.5 for e in false_starts)
```

### Test 2 — Compression ratio

```python
def test_compression_ratio_bounds():
    """Vérifie qu'on ne coupe pas trop de contenu."""
    transcript = TranscriptFixture.standard_10min()
    cut_list = run_full_pipeline(transcript, aggressiveness="medium")
    
    assert 0.5 <= cut_list.compression_ratio <= 1.0
    # On ne devrait jamais couper plus de 50% en mode medium
```

### Test 3 — Validation Pydantic

```python
def test_cut_list_schema_validation():
    """Vérifie que la CutList valide bien les schémas."""
    with pytest.raises(ValidationError):
        CutList(
            version="1.0.0",
            source_duration=-1.0,  # Négatif → doit échouer
            kept_segments=[],
            removed_segments=[],
            b_roll_suggestions=[],
            total_kept_duration=0,
            total_removed_duration=0,
            compression_ratio=1.5,  # > 1.0 → doit échouer
        )
```

### Test 4 — Fallback LLM

```python
@patch("narrative_analyzer.llm_client.OpenRouterClient.analyze")
def test_llm_fallback_on_timeout(mock_analyze):
    """Vérifie le fallback vers DeepSeek quand Qwen timeout."""
    mock_analyze.side_effect = TimeoutError("Qwen timeout")
    client = LLMClient()
    
    result = client.analyze_with_fallback(transcript)
    # Doit avoir utilisé le fallback sans erreur
    assert result is not None
    assert len(result.errors) > 0
```

---

## 12. Pièges connus

### ⚠️ Hallucination de timestamps par le LLM

**Problème** : Le LLM peut retourner des timestamps qui n'existent pas dans le transcript original (hallucination numérique).

**Mitigation** : Validation stricte post-LLM : tout timestamp hors bornes est corrigé en recherchant le mot le plus proche dans les segments. Si aucun mot proche trouvé, l'erreur est rejetée avec log.

### ⚠️ Sur-dérushage en mode "high"

**Problème** : Un `aggressiveness: "high"` peut couper les pauses comiques ou dramatiques, rendant la vidéo artificielle.

**Mitigation** : Logger le `compression_ratio` et lever un warning si < 0.5 (plus de la moitié du contenu coupé). Configurer `keep_natural_pauses: true` pour protéger les silences expressifs.

### ⚠️ B-rolls à chaque phrase

**Problème** : Le LLM peut suggérer des B-rolls à chaque phrase, créant une vidéo surchargée visuellement.

**Mitigation** : Limite configurable de 1 B-roll toutes les 30-50s. Déduplication par similarité de concept. Éviter les B-rolls sur les punchlines.

### ⚠️ Ponctuation manquante de WhisperX

**Problème** : WhisperX ne met pas toujours les points et virgules, rendant la segmentation en phrases difficile.

**Mitigation** : Le `script_cleaner` doit inférer la ponctuation par l'analyse des pauses longues (> 0.5s = virgule, > 1.0s = point). Le LLM peut aussi ajouter de la ponctuation lors du nettoyage.

### ⚠️ Double négociation de sens avec le LLM

**Problème** : Le LLM peut interpréter une pause dramatique comme un silence mort, ou une répétition rhétorique comme un bégaiement.

**Mitigation** : Ajouter des exemples de cas limites dans le prompt système. Le cut_engine a toujours le dernier mot sur les décisions temporelles. Un mode "conservatif" par défaut (garder plutôt que couper en cas de doute).
