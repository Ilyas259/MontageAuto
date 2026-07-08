# Agent #1 — Acquisition & Transcription

> **Module** : Acquisition & Transcription  
> **Version** : 1.0.0  
> **Auteur** : Redd  
> **Pipeline** : Montage vidéo automatisé  
> **Entrée** : Fichier vidéo brut (MP4/MOV)  
> **Sortie** : `transcript.json` (mots, timestamps, silences, speakers)

---

## 1. Résumé

L'Agent #1 est le premier maillon du pipeline de montage vidéo automatisé. Il lit un fichier vidéo brut (MP4 ou MOV), en extrait la piste audio, et produit un fichier `transcript.json` structuré contenant :

- Le texte parlé, **mot-à-mot avec timestamps** (word-level)
- Les **segments de silence** détectés et timecodés
- L'**identification du locuteur** (speaker diarization)
- La **ponctuation inférée**
- Le **score de confiance Whisper** par mot

Trois moteurs travaillent en parallèle puis fusionnent leurs résultats :
| Moteur | Rôle | Type |
|--------|------|------|
| **ElevenLabs Scribe V2** | Transcription primaire — meilleure sur les noms propres | API REST |
| **WhisperX** | Transcription secondaire alignée — mots + timestamps + silences + diarization | Local (CPU) |
| **Silero VAD** | Détection de silence complémentaire — résolution fine | Local (CPU) |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Agent #1 — Acquisition                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Fichier brut ───► Audio Extractor ───► Audio PCM 16kHz     │
│       │                                    │                │
│       │                          ┌─────────┼─────────┐      │
│       │                          │         │         │      │
│       │                    ┌─────▼──┐ ┌───▼────┐ ┌──▼───┐ │
│       │                    │ Scribe │ │WhisperX│ │ VAD  │ │
│       │                    │  V2    │ │ (local)│ │      │ │
│       │                    │ (API)  │ │        │ │      │ │
│       │                    └───┬────┘ └───┬────┘ └──┬───┘ │
│       │                        │          │          │     │
│       │                        └─────┬────┘          │     │
│       │                              │               │     │
│       │                    ┌─────────▼───────────────▼──┐  │
│       │                    │        Fusion Engine        │  │
│       │                    │  (Scribe texte + WhisperX   │  │
│       │                    │   timestamps + VAD silence) │  │
│       │                    └─────────────┬───────────────┘  │
│       │                                  │                  │
│       │                    ┌─────────────▼───────────────┐  │
│       │                    │      transcript.json        │  │
│       │                    │  (Agent #2 ← lit ce fichier)│  │
│       │                    └─────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Flux de données

1. **Extraction audio** : `ffmpeg` extrait la piste audio en PCM 16 kHz mono
2. **Parallélisation** : Les 3 analyseurs reçoivent le même fichier audio
3. **Scribe V2** : Transcription haute-fidélité via API → `scribe_result`
4. **WhisperX** : Transcription alignée locale → `whisperx_result`
5. **VAD** : Détection de silence granulaire → `vad_result`
6. **Fusion** : L'algorithme de fusion intelligente combine les 3 résultats
7. **Normalisation** : Production du `transcript.json` final

---

## 3. Structure du Module

```
agent1_transcription/
├── __init__.py
├── main.py                          # Point d'entrée CLI
├── config.py                        # Configuration (API keys, chemins, timeout)
├── models/
│   ├── __init__.py
│   ├── audio.py                     # AudioInput, AudioInfo
│   ├── scribe.py                    # ScribeResult, ScribeWord, ScribeSegment
│   ├── whisperx.py                  # WhisperXResult, WhisperXWord, WhisperXSegment
│   ├── vad.py                       # VADResult, VADSegment
│   ├── fusion.py                    # FusionConfig, FusionStrategy
│   └── transcript.py                # Transcript (sortie finale), Word, Silence, Speaker
├── audio/
│   ├── __init__.py
│   └── extractor.py                 # Extraction audio avec ffmpeg
├── scribe/
│   ├── __init__.py
│   ├── client.py                    # Client API ElevenLabs Scribe V2
│   └── cache.py                     # Cache local des transcriptions Scribe
├── whisperx/
│   ├── __init__.py
│   ├── transcribe.py                # Lancement WhisperX (CPU, tiny/base)
│   └── alignment.py                 # Alignement forcé (phonème → mot)
├── vad/
│   ├── __init__.py
│   └── detector.py                  # Détecteur de silence (Silero VAD)
├── fusion/
│   ├── __init__.py
│   ├── engine.py                    # Moteur de fusion principal
│   ├── aligner.py                   # Alignement temporel Scribe ↔ WhisperX
│   ├── conflict.py                  # Résolution de conflits de timestamps
│   └── normalizer.py               # Normalisation → transcript.json
├── utils/
│   ├── __init__.py
│   ├── logger.py                    # Logging structuré
│   ├── progress.py                  # Barre de progression
│   └── time.py                      # Utilitaires temporels (formatage, comparaison)
├── tests/
│   ├── __init__.py
│   ├── test_audio_extractor.py
│   ├── test_scribe_client.py
│   ├── test_whisperx_transcribe.py
│   ├── test_vad_detector.py
│   ├── test_fusion_engine.py
│   ├── test_aligner.py
│   ├── test_conflict.py
│   ├── test_normalizer.py
│   ├── test_integration.py
│   └── fixtures/
│       ├── sample_audio.wav
│       ├── scribe_response.json
│       ├── whisperx_output.json
│       └── vad_output.json
├── requirements.txt
└── pyproject.toml
```

---

## 4. Schémas Pydantic

### 4.1 AudioInput / AudioInfo (`models/audio.py`)

```python
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional

class AudioInfo(BaseModel):
    """Informations sur le fichier audio extrait."""
    file_path: Path
    sample_rate: int = 16000          # 16 kHz obligatoire
    channels: int = 1                 # Mono obligatoire
    duration_seconds: float
    bit_depth: int = 16

class AudioInput(BaseModel):
    """Entrée du pipeline — fichier vidéo brut."""
    video_path: Path
    audio_output_dir: Path            # Dossier pour l'audio extrait
    language: str = "fr"              # Langue de la transcription
    whisperx_model: str = "tiny"      # tiny ou base (CPU)
    force_reprocess: bool = False     # Ignorer le cache
```

### 4.2 Scribe Result (`models/scribe.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ScribeWord(BaseModel):
    """Mot individuel transcrit par Scribe V2."""
    text: str
    start: float                      # Timestamp début (secondes)
    end: float                        # Timestamp fin (secondes)
    confidence: float = Field(ge=0.0, le=1.0)
    speaker_id: Optional[str] = None

class ScribeSegment(BaseModel):
    """Segment de phrase transcrit par Scribe V2."""
    text: str                         # Texte ponctué
    start: float
    end: float
    words: List[ScribeWord]
    speaker_id: Optional[str] = None
    language: str = "fr"

class ScribeResult(BaseModel):
    """Résultat complet de l'API Scribe V2."""
    segments: List[ScribeSegment]
    full_text: str
    language: str = "fr"
    language_confidence: float = Field(ge=0.0, le=1.0)
    processing_time_ms: Optional[int] = None
    api_call_id: Optional[str] = None
    cached: bool = False
```

### 4.3 WhisperX Result (`models/whisperx.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class WhisperXWord(BaseModel):
    """Mot individuel aligné par WhisperX."""
    text: str
    start: float                      # Timestamp début (secondes)
    end: float                        # Timestamp fin (secondes)
    confidence: float = Field(ge=0.0, le=1.0)
    speaker_id: Optional[str] = None

class WhisperXSilence(BaseModel):
    """Segment de silence détecté par WhisperX."""
    start: float
    end: float
    duration_seconds: float

class WhisperXSegment(BaseModel):
    """Segment de parole détecté par WhisperX."""
    text: str
    start: float
    end: float
    words: List[WhisperXWord]
    speaker_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

class WhisperXResult(BaseModel):
    """Résultat complet de WhisperX."""
    segments: List[WhisperXSegment]
    word_segments: List[WhisperXWord]
    silences: List[WhisperXSilence]
    language: str = "fr"
    model_name: str = "tiny"          # tiny ou base
    processing_time_seconds: float
    speakers_detected: int = 1
```

### 4.4 VAD Result (`models/vad.py`)

```python
from pydantic import BaseModel, Field
from typing import List

class VADSegment(BaseModel):
    """Segment VAD (voix ou silence)."""
    start: float
    end: float
    is_speech: bool
    confidence: float = Field(ge=0.0, le=1.0)

class VADResult(BaseModel):
    """Résultat complet du détecteur VAD."""
    segments: List[VADSegment]
    sample_rate: int = 16000
    frame_duration_ms: int = 30       # Résolution temporelle
    processing_time_ms: float
    silence_segments: List[VADSegment]  # Filtre: seulement les silences
    speech_segments: List[VADSegment]   # Filtre: seulement la parole
```

### 4.5 Transcript Final (`models/transcript.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class Word(BaseModel):
    """Mot individuel dans la sortie finale."""
    text: str                         # Texte Scribe (corrigé)
    start: float                      # Timestamp WhisperX (aligné)
    end: float                        # Timestamp WhisperX (aligné)
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["scribe", "whisperx", "fused"] = "fused"

class Silence(BaseModel):
    """Segment de silence dans la sortie finale."""
    start: float
    end: float
    duration_seconds: float
    source: Literal["whisperx", "vad", "fused"] = "fused"
    confidence: float = Field(ge=0.0, le=1.0)

class Sentence(BaseModel):
    """Phrase complète avec ponctuation."""
    text: str
    start: float
    end: float
    words: List[Word]
    speaker_id: Optional[str] = None

class SpeakerInfo(BaseModel):
    """Information sur un locuteur."""
    speaker_id: str = "SPEAKER_00"
    total_words: int = 0
    total_duration_seconds: float = 0.0
    segment_count: int = 0

class Transcript(BaseModel):
    """Sortie finale de l'Agent #1 — transcript.json."""
    # Métadonnées
    video_filename: str
    duration_seconds: float
    language: str = "fr"
    processing_timestamp: datetime = Field(default_factory=datetime.now)
    agent_version: str = "1.0.0"
    
    # Corpus
    words: List[Word]
    silences: List[Silence]
    sentences: List[Sentence]
    speakers: List[SpeakerInfo]
    
    # Métriques
    total_words: int
    total_silences: int
    average_confidence: float = Field(ge=0.0, le=1.0)
    processing_time_seconds: float
    
    model_config = {"extra": "forbid"}
```

---

## 5. Algorithme de Fusion Scribe / WhisperX / VAD

### 5.1 Principe Général

Chaque moteur a des forces complémentaires :

| Moteur | Forces | Faiblesses |
|--------|--------|------------|
| **Scribe V2** | Texte précis (noms propres, jargon), ponctuation naturelle, API rapide | Timestamps moins précis (~200ms d'offset), coût API, dépendance réseau |
| **WhisperX** | Timestamps mot-à-mot précis, silences timecodés, diarization, fonctionnement local | Texte moins fiable (hallucinations sur mots rares), lent sur CPU |
| **VAD** | Détection silence granulaire (<30ms), léger, local | Pas de transcription, binaire (parole/silence uniquement) |

**La fusion prend le meilleur de chaque monde** : le texte de Scribe, les timestamps de WhisperX, les silences fins du VAD.

### 5.2 Pseudocode détaillé

```
FUNCTION fusionner(scribe_result, whisperx_result, vad_result, config)
    // ÉTAPE 1 : Alignement temporel Scribe ↔ WhisperX
    // Scribe peut avoir un offset de ~200ms. On calcule le décalage
    // en corrélant les timestamps des mots communs.
    offset_ms = calculer_offset_scribe(scribe_result, whisperx_result)
    scribe_calibré = appliquer_offset(scribe_result, offset_ms)
    
    // ÉTAPE 2 : Fusion mot-à-mot
    // Pour chaque mot, on prend le TEXTE de Scribe (plus fiable)
    // et le TIMESTAMP de WhisperX (plus précis, aligné).
    words_fusion = []
    pour chaque mot_scribe dans scribe_calibré.words:
        mot_whisper = trouver_plus_proche(whisperx_result.words, 
                                         mot_scribe.timestamp, 
                                         seuil_ms=150)
        si mot_whisper existe:
            words_fusion.add(Word(
                text = mot_scribe.text,                   // Texte Scribe
                start = mot_whisper.start,                // Timestamp WhisperX
                end = mot_whisper.end,                    // Timestamp WhisperX
                confidence = min(mot_scribe.confidence,    // Score prudent
                                 mot_whisper.confidence),
                source = "fused"
            ))
        sinon:
            // Mot Scribe non aligné → on garde timestamp Scribe calibré
            words_fusion.add(Word(
                text = mot_scribe.text,
                start = mot_scribe.start,
                end = mot_scribe.end,
                confidence = mot_scribe.confidence * 0.8,  // Pénalité
                source = "scribe"
            ))
    
    // ÉTAPE 3 : Détection des mots "fantômes" WhisperX
    // WhisperX peut inventer des mots à basse confiance (< 0.3)
    // On ne les inclut PAS dans la sortie finale.
    pour chaque mot_whisper dans whisperx_result.words:
        si mot_whisper.confidence < SEUIL_HALLUCINATION (0.3):
            mot_correspondant = trouver_scribe_proche(words_fusion, mot_whisper.timestamp)
            si aucun mot_scribe trouvé:
                logger.warning(f"Mot fantôme WhisperX ignoré: '{mot_whisper.text}' @ {mot_whisper.start}s")
    
    // ÉTAPE 4 : Fusion des silences
    // WhisperX donne des silences larges, VAD donne des silences fins.
    // On fusionne en gardant la résolution la plus fine.
    silences_fusion = []
    
    // 4a: Prendre les silences WhisperX comme base
    pour chaque silence_wx dans whisperx_result.silences:
        // 4b: Intersecter avec silences VAD pour validation
        silences_vad_dans_intervalle = vad_result.segments.filter(
            s.start >= silence_wx.start ET s.end <= silence_wx.end ET s.is_speech == False
        )
        
        si silences_vad_dans_intervalle.non_vide:
            // 4c: Découper le silence WhisperX selon les frontières VAD
            sous_segments = découper_selon_vad(silence_wx, silences_vad_dans_intervalle)
            pour chaque ss dans sous_segments:
                si ss.duration_seconds >= SEUIL_SILENCE_MIN (0.1):  // 100ms min
                    silences_fusion.add(Silence(
                        start = ss.start,
                        end = ss.end,
                        duration_seconds = ss.duration,
                        source = "fused",
                        confidence = confiance_vad_dans_intervalle(ss)
                    ))
        sinon:
            si silence_wx.duration_seconds >= SEUIL_SILENCE_MIN:
                silences_fusion.add(Silence(
                    start = silence_wx.start,
                    end = silence_wx.end,
                    duration_seconds = silence_wx.duration_seconds,
                    source = "whisperx",
                    confidence = 0.5  // Non validé par VAD
                ))
    
    // ÉTAPE 5 : Reconstruction des phrases (sentences)
    // À partir des mots fusionnés + silences longs > 500ms
    sentences = reconstruire_phrases(words_fusion, silences_fusion)
    
    // ÉTAPE 6 : Assignation des speakers
    speaker_info = assigner_speakers(words_fusion, whisperx_result)
    
    // ÉTAPE 7 : Normalisation et construction du Transcript final
    transcript = Transcript(
        words = words_fusion,
        silences = silences_fusion,
        sentences = sentences,
        speakers = speaker_info,
        total_words = len(words_fusion),
        total_silences = len(silences_fusion),
        ...
    )
    
    RETOURNER transcript
```

### 5.3 Algorithme d'Alignement Temporel (détail)

```python
def calculer_offset_scribe(scribe: ScribeResult, whisperx: WhisperXResult) -> float:
    """
    Calcule le décalage temporel entre Scribe et WhisperX.
    
    Méthode : On prend les N premiers mots communs (même texte approximatif,
    après lowercase + strip) et on calcule la médiane des différences de start.
    
    Retourne l'offset en secondes (positif = Scribe est en avance).
    """
    mots_communs = []
    for sw, wxw in zip(scribe.words[:50], whisperx.word_segments[:50]):
        if sw.text.lower().strip() == wxw.text.lower().strip():
            mots_communs.append({
                'word': sw.text,
                'scribe_start': sw.start,
                'whisperx_start': wxw.start,
                'diff': sw.start - wxw.start
            })
    
    if len(mots_communs) < 5:
        return 0.0  # Pas assez de points pour un alignement fiable
    
    # Médiane robuste aux outliers
    diffs = sorted([m['diff'] for m in mots_communs])
    return diffs[len(diffs) // 2]
```

### 5.4 Résolution de Conflits de Timestamps

| Scénario | Résolution |
|----------|-----------|
| Scribe et WhisperX donnent un mot au même endroit (±150ms) | **Timestamp WhisperX** (plus précis pour l'alignement) |
| Scribe a un mot que WhisperX n'a pas | **Timestamp Scribe** (calibré de l'offset global) |
| WhisperX a un mot que Scribe n'a pas (confiance > 0.5) | **Inclusion avec source = whisperx** et note "non vérifié Scribe" |
| WhisperX a un mot que Scribe n'a pas (confiance < 0.3) | **Rejet** (hallucination probable) |
| Désaccord texte (Scribe="Anthropic", WhisperX="anthropique") | **Texte Scribe** conservé, alerte log |

### 5.5 Stratégie de Découpage des Silences

```
Critères de fusion VAD + WhisperX :
- Silence < 100ms  →  Filtré (bruit de fond, respiration)
- Silence 100-500ms →  Considéré silence si VAD confirme (confiance > 0.7)
- Silence 500ms+   →  Toujours conservé (césure entre phrases)
- Plusieurs silences VAD consécutifs →  Fusionnés si < 50ms d'écart
```

---

## 6. Interface CLI

### 6.1 Commande principale

```bash
python -m agent1_transcription transcribe \
    --video /chemin/video.mp4 \
    --output ./output/transcript.json \
    --language fr \
    --whisperx-model tiny \
    --force-reprocess
```

### 6.2 Arguments

| Argument | Type | Défaut | Description |
|----------|------|--------|-------------|
| `--video` | `Path` | **Requis** | Chemin du fichier vidéo (MP4/MOV) |
| `--output` | `Path` | `./output/transcript.json` | Chemin de sortie du transcript |
| `--language` | `str` | `fr` | Langue ISO 639-1 |
| `--whisperx-model` | `Literal[tiny, base]` | `tiny` | Modèle WhisperX (CPU) |
| `--force-reprocess` | `Flag` | `False` | Ignorer le cache Scribe |
| `--vad-threshold` | `float` | `0.5` | Seuil de décision VAD (0.0-1.0) |
| `--silence-min-ms` | `int` | `100` | Seuil minimum de silence (ms) |
| `--log-level` | `str` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `--api-timeout` | `int` | `120` | Timeout API Scribe (secondes) |
| `--max-retries` | `int` | `3` | Tentatives API max |

### 6.3 Sortie console

```
╭──────────────────────────────────────────────╮
│  Agent #1 — Acquisition & Transcription      │
│  v1.0.0                                      │
├──────────────────────────────────────────────┤
│  Vidéo   : interview_redd.mp4                │
│  Durée   : 00:12:34                          │
│  Langue  : fr                                │
├──────────────────────────────────────────────┤
│  ▶ Extraction audio...  ✓  (2.3s)            │
│  ▶ Scribe V2 (API)...   ✓  (8.1s) [cached]  │
│  ▶ WhisperX (CPU)...    ████████░░ 82%       │
│  ▶ VAD...               ✓  (0.8s)            │
│  ▶ Fusion...            ✓  (0.4s)            │
├──────────────────────────────────────────────┤
│  Résultats :                                 │
│  • Mots        : 1 847                       │
│  • Silences    : 143                         │
│  • Phrases     : 89                          │
│  • Speakers    : 2                           │
│  • Conf. moy.  : 0.89                        │
│  • Temps total : 45.2s                       │
│                                              │
│  ✓ Transcript → /output/transcript.json      │
╰──────────────────────────────────────────────╯
```

---

## 7. Implémentation Détaillée

### 7.1 Extraction Audio (`audio/extractor.py`)

```python
import asyncio
import subprocess
from pathlib import Path
from models.audio import AudioInfo

class AudioExtractor:
    """Extrait la piste audio d'une vidéo en PCM 16kHz mono."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
    
    async def extract(self, video_path: Path, output_dir: Path) -> AudioInfo:
        output_path = output_dir / f"{video_path.stem}_audio.wav"
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-vn",                    # Pas de video
            "-acodec", "pcm_s16le",   # PCM 16-bit
            "-ar", "16000",            # 16 kHz
            "-ac", "1",                # Mono
            str(output_path)
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")
        
        # Récupérer la durée avec ffprobe
        duration = await self._get_duration(video_path)
        
        return AudioInfo(
            file_path=output_path,
            sample_rate=16000,
            channels=1,
            duration_seconds=duration,
            bit_depth=16
        )
```

### 7.2 Client Scribe V2 (`scribe/client.py`)

```python
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Optional
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.scribe import ScribeResult
from scribe.cache import ScribeCache

API_URL = "https://api.elevenlabs.io/v1/scribe"
MAX_RETRIES = 3
TIMEOUT = 120  # secondes

class ScribeClient:
    """Client pour l'API ElevenLabs Scribe V2."""
    
    def __init__(self, api_key: str, cache_dir: Optional[Path] = None):
        self.api_key = api_key
        self.cache = ScribeCache(cache_dir) if cache_dir else None
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def transcribe(self, audio_path: Path, language: str = "fr") -> ScribeResult:
        # Vérifier le cache
        cache_key = self._compute_cache_key(audio_path, language)
        if self.cache and not force_reprocess:
            cached = await self.cache.get(cache_key)
            if cached:
                cached.cached = True
                return cached
        
        # Appel API
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with open(audio_path, "rb") as f:
                form_data = aiohttp.FormData()
                form_data.add_field("file", f, filename=audio_path.name)
                form_data.add_field("model_id", "scribe_v2")
                form_data.add_field("language", language)
                form_data.add_field("diarize", "true")
                
                headers = {"xi-api-key": self.api_key}
                
                async with session.post(API_URL, headers=headers, data=form_data) as resp:
                    if resp.status != 200:
                        error_body = await resp.text()
                        raise RuntimeError(f"Scribe API error {resp.status}: {error_body}")
                    
                    data = await resp.json()
                    result = self._parse_response(data)
        
        # Mettre en cache
        if self.cache:
            await self.cache.set(cache_key, result)
        
        return result
```

### 7.3 Cache Scribe (`scribe/cache.py`)

```python
import hashlib
import json
import pickle
from pathlib import Path
from typing import Optional
from models.scribe import ScribeResult

class ScribeCache:
    """
    Cache local des transcriptions Scribe.
    
    Stratégie :
    - Clé = hash SHA256 du fichier audio + langue
    - Stockage = fichier pickle dans ~/.cache/agent1/scribe/
    - Durée de vie : illimitée (le fichier audio ne change pas)
    - Invalidation : via --force-reprocess ou suppression manuelle
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "agent1" / "scribe"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _key_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.pkl"
    
    async def get(self, cache_key: str) -> Optional[ScribeResult]:
        path = self._key_path(cache_key)
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return None
    
    async def set(self, cache_key: str, result: ScribeResult):
        path = self._key_path(cache_key)
        with open(path, "wb") as f:
            pickle.dump(result, f)
    
    @staticmethod
    def compute_key(audio_path: Path, language: str) -> str:
        """Hash SHA256 du contenu audio + langue."""
        hasher = hashlib.sha256()
        with open(audio_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        hasher.update(language.encode())
        return hasher.hexdigest()
```

### 7.4 WhisperX Local (`whisperx/transcribe.py`)

```python
import time
import logging
from pathlib import Path
from typing import Optional
import whisperx
import torch

from models.whisperx import WhisperXResult, WhisperXWord, WhisperXSegment, WhisperXSilence

logger = logging.getLogger(__name__)

class WhisperXTranscriber:
    """
    Transcription WhisperX en local (CPU uniquement).
    
    Modèles disponibles :
    - "tiny" : Rapide, ~1 Go RAM, précis pour timestamps
    - "base" : Plus lent, ~1.5 Go RAM, légèrement meilleur
    
    Attention : WhisperX en CPU est lent (~5-10x le temps réel).
    Toujours logger l'avancement avec une barre de progression.
    """
    
    def __init__(self, model_name: str = "tiny", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None  # Lazy loading
    
    def _load_model(self):
        if self.model is None:
            logger.info(f"Chargement WhisperX model={self.model_name} device={self.device}...")
            self.model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type="float32",  # CPU only
                language="fr"
            )
            logger.info("WhisperX chargé avec succès.")
    
    async def transcribe(self, audio_path: Path, language: str = "fr") -> WhisperXResult:
        self._load_model()
        start_time = time.time()
        
        # Étape 1 : Transcription
        audio = whisperx.load_audio(str(audio_path))
        result = self.model.transcribe(audio, batch_size=16, language=language)
        
        # Étape 2 : Alignement (forcé)
        # Nécessaire pour des timestamps mot-à-mot précis
        model_a, metadata = whisperx.load_align_model(language_code=language, device=self.device)
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, self.device,
            return_char_alignments=False
        )
        
        # Étape 3 : Diarization
        # Si un modèle de diarization est disponible
        try:
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=self.device)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
        except Exception as e:
            logger.warning(f"Diarization non disponible: {e}")
        
        # Étape 4 : Extraction des silences
        # WhisperX ne fournit pas directement les silences → on les calcule
        # à partir des écarts entre segments
        silences = self._extract_silences(result["segments"])
        
        # Parsing
        segments = []
        word_segments = []
        for seg in result["segments"]:
            wx_seg = WhisperXSegment(
                text=seg.get("text", ""),
                start=seg["start"],
                end=seg["end"],
                words=[],
                speaker_id=seg.get("speaker", None),
                confidence=seg.get("confidence", 0.5)
            )
            for word in seg.get("words", []):
                wx_word = WhisperXWord(
                    text=word["text"],
                    start=word["start"],
                    end=word["end"],
                    confidence=word.get("score", 0.5),
                    speaker_id=word.get("speaker", None)
                )
                wx_seg.words.append(wx_word)
                word_segments.append(wx_word)
            segments.append(wx_seg)
        
        elapsed = time.time() - start_time
        logger.info(f"WhisperX terminé en {elapsed:.1f}s ({len(word_segments)} mots, {len(silences)} silences)")
        
        return WhisperXResult(
            segments=segments,
            word_segments=word_segments,
            silences=silences,
            language=language,
            model_name=self.model_name,
            processing_time_seconds=elapsed,
            speakers_detected=len(set(
                w.speaker_id for w in word_segments if w.speaker_id
            )) or 1
        )
    
    def _extract_silences(self, segments: list) -> list[WhisperXSilence]:
        """Extrait les silences entre les segments de parole."""
        silences = []
        for i in range(len(segments) - 1):
            gap_start = segments[i]["end"]
            gap_end = segments[i + 1]["start"]
            duration = gap_end - gap_start
            if duration > 0.05:  # > 50ms
                silences.append(WhisperXSilence(
                    start=gap_start,
                    end=gap_end,
                    duration_seconds=duration
                ))
        return silences
```

### 7.5 Détecteur VAD (`vad/detector.py`)

```python
import time
import logging
from pathlib import Path
from typing import List
import torch
import silero_vad

from models.vad import VADResult, VADSegment

logger = logging.getLogger(__name__)

class VADDetector:
    """
    Détecteur de silence basé sur Silero VAD.
    
    Avantages par rapport à webrtcvad :
    - Plus robuste au bruit de fond
    - Meilleure détection des fins de mots
    - Support natif des trames longues (30ms, 60ms, 100ms)
    - Modèle entrainé sur du français
    
    Résolution temporelle : 30ms (configurable via frame_duration_ms)
    """
    
    def __init__(self, threshold: float = 0.5, frame_duration_ms: int = 30):
        self.threshold = threshold
        self.frame_duration_ms = frame_duration_ms
        self.model = None  # Lazy loading
    
    def _load_model(self):
        if self.model is None:
            logger.info("Chargement Silero VAD...")
            self.model = silero_vad.load_silero_vad()
            logger.info("Silero VAD chargé.")
    
    async def detect(self, audio_path: Path) -> VADResult:
        """
        Détecte les segments de parole et silence dans un fichier audio.
        
        Retourne une liste de segments avec label is_speech = True/False.
        """
        self._load_model()
        start_time = time.time()
        
        # Charger l'audio
        audio = silero_vad.read_audio(str(audio_path), sampling_rate=16000)
        
        # Détection VAD
        speech_probs = self.model.get_speech_timestamps(
            audio,
            sampling_rate=16000,
            threshold=self.threshold,
            min_speech_duration_ms=100,
            min_silence_duration_ms=30,  # Résolution fine
            return_seconds=True
        )
        
        # Convertir en segments VAD
        segments = self._probs_to_segments(speech_probs, len(audio) / 16000)
        
        elapsed = time.time() - start_time
        logger.info(f"VAD terminé en {elapsed:.2f}s ({len(segments)} segments)")
        
        silence_segments = [s for s in segments if not s.is_speech]
        speech_segments = [s for s in segments if s.is_speech]
        
        return VADResult(
            segments=segments,
            sample_rate=16000,
            frame_duration_ms=self.frame_duration_ms,
            processing_time_ms=elapsed * 1000,
            silence_segments=silence_segments,
            speech_segments=speech_segments
        )
    
    def _probs_to_segments(self, speech_timestamps: list, total_duration: float) -> List[VADSegment]:
        """
        Convertit les timestamps de parole en segments VAD continus.
        """
        segments = []
        last_end = 0.0
        
        for ts in speech_timestamps:
            # Silence avant ce segment de parole
            if ts['start'] > last_end + 0.01:
                segments.append(VADSegment(
                    start=last_end,
                    end=ts['start'],
                    is_speech=False,
                    confidence=1.0 - self.threshold
                ))
            
            # Segment de parole
            segments.append(VADSegment(
                start=ts['start'],
                end=ts['end'],
                is_speech=True,
                confidence=ts.get('confidence', self.threshold)
            ))
            
            last_end = ts['end']
        
        # Silence après le dernier segment
        if last_end < total_duration:
            segments.append(VADSegment(
                start=last_end,
                end=total_duration,
                is_speech=False,
                confidence=1.0 - self.threshold
            ))
        
        return segments
```

### 7.6 Moteur de Fusion Principal (`fusion/engine.py`)

```python
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from models.audio import AudioInput, AudioInfo
from models.scribe import ScribeResult
from models.whisperx import WhisperXResult
from models.vad import VADResult
from models.transcript import Transcript

from audio.extractor import AudioExtractor
from scribe.client import ScribeClient
from whisperx.transcribe import WhisperXTranscriber
from vad.detector import VADDetector
from fusion.aligner import align_scribe_whisperx
from fusion.conflict import resolve_timestamp_conflicts
from fusion.normalizer import normalize_to_transcript

logger = logging.getLogger(__name__)

class FusionEngine:
    """
    Orchestre les 3 moteurs de transcription et fusionne leurs résultats.
    
    Le pipeline complet :
    1. Extraire l'audio
    2. Lancer Scribe V2 (API), WhisperX (local), VAD (local) en parallèle
    3. Aligner Scribe ↔ WhisperX
    4. Résoudre les conflits de timestamps
    5. Fusionner les silences WhisperX + VAD
    6. Normaliser → Transcript
    """
    
    def __init__(self, config: "Agent1Config"):
        self.config = config
        self.extractor = AudioExtractor()
        self.scribe = ScribeClient(
            api_key=config.ELEVENLABS_API_KEY,
            cache_dir=config.cache_dir / "scribe"
        )
        self.whisperx = WhisperXTranscriber(
            model_name=config.whisperx_model,
            device="cpu"
        )
        self.vad = VADDetector(
            threshold=config.vad_threshold,
            frame_duration_ms=30
        )
    
    async def process(self, video_path: Path) -> Transcript:
        """
        Traite une vidéo et retourne le Transcript final.
        """
        start_time = time.time()
        
        # 1. Extraction audio
        logger.info(f"Extraction audio de {video_path.name}...")
        audio = await self.extractor.extract(
            video_path,
            self.config.audio_cache_dir
        )
        
        # 2. Lancement parallèle des 3 analyseurs
        logger.info("Lancement Scribe V2, WhisperX, VAD en parallèle...")
        scribe_task = self.scribe.transcribe(audio.file_path, self.config.language)
        whisperx_task = self.whisperx.transcribe(audio.file_path, self.config.language)
        vad_task = self.vad.detect(audio.file_path)
        
        scribe_result, whisperx_result, vad_result = await asyncio.gather(
            scribe_task, whisperx_task, vad_task
        )
        
        logger.info(
            f"Scribe: {len(scribe_result.words)} mots | "
            f"WhisperX: {len(whisperx_result.word_segments)} mots, "
            f"{len(whisperx_result.silences)} silences | "
            f"VAD: {len(vad_result.segments)} segments"
        )
        
        # 3. Alignement Scribe ↔ WhisperX
        aligned = align_scribe_whisperx(scribe_result, whisperx_result)
        
        # 4. Résolution des conflits de timestamps
        resolved = resolve_timestamp_conflicts(
            aligned, whisperx_result, self.config.silence_min_ms / 1000.0
        )
        
        # 5. Normalisation → Transcript
        transcript = normalize_to_transcript(
            resolved=resolved,
            scribe=scribe_result,
            whisperx=whisperx_result,
            vad=vad_result,
            video_path=video_path,
            audio_duration=audio.duration_seconds,
            processing_time=time.time() - start_time,
            config=self.config
        )
        
        return transcript
```

---

## 8. Configuration (`config.py`)

```python
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

class Agent1Config(BaseSettings):
    """Configuration de l'Agent #1 via variables d'environnement ou .env."""
    
    # ElevenLabs
    ELEVENLABS_API_KEY: str
    
    # Chemins
    output_dir: Path = Path("./output")
    audio_cache_dir: Path = Path("./cache/audio")
    cache_dir: Path = Path.home() / ".cache" / "agent1"
    
    # Paramètres transcription
    language: str = "fr"
    whisperx_model: str = "tiny"         # "tiny" ou "base"
    force_reprocess: bool = False
    
    # VAD
    vad_threshold: float = 0.5
    vad_frame_duration_ms: int = 30
    
    # Fusion
    silence_min_ms: int = 100            # Seuil minimum de silence
    alignment_seuil_ms: float = 150.0    # Fenêtre d'alignement scribe↔whisperx
    hallucination_threshold: float = 0.3 # Seuil de rejet "mot fantôme"
    
    # API
    api_timeout: int = 120               # secondes
    max_retries: int = 3
    
    # Logging
    log_level: str = "INFO"
    show_progress_bar: bool = True
    
    model_config = {"env_file": ".env", "env_prefix": "AGENT1_"}
```

---

## 9. Tests et Validation

### 9.1 Tests Unitaires

| Module | Test | Description |
|--------|------|-------------|
| **audio/extractor** | `test_extract_pcm` | Vérifie la sortie PCM 16kHz mono |
| | `test_extract_invalid_file` | Erreur sur fichier inexistant |
| | `test_duration_ffprobe` | Précision de la détection de durée |
| **scribe/client** | `test_api_success` | Mock API → parsing correct |
| | `test_api_retry` | 2 échecs → 3e tentative réussie |
| | `test_api_timeout` | Timeout → retry |
| | `test_cache_hit` | Cache → pas d'appel API |
| | `test_cache_miss` | Pas de cache → appel API |
| **whisperx/transcribe** | `test_transcribe_tiny` | Transcription avec modèle tiny |
| | `test_silence_extraction` | Silences correctement extraits |
| | `test_diarization_fallback` | Pas crash si diarization indisponible |
| | `test_cpu_large_file` | Gestion fichier long (CPU) |
| **vad/detector** | `test_vad_speech` | Parole détectée correctement |
| | `test_vad_silence` | Silence détecté correctement |
| | `test_vad_threshold` | Seuil bas → plus de "parole" |
| | `test_vad_noise_rejection` | Bruit de fond < 100ms filtré |
| **fusion/engine** | `test_full_pipeline` | Pipeline complet (mock API) |
| **fusion/aligner** | `test_offset_calculation` | Offset Scribe correctement calculé |
| | `test_alignment_perfect` | Pas de décalage → pas d'ajustement |
| | `test_alignment_200ms` | Décalage 200ms → corrigé |
| **fusion/conflict** | `test_hallucination_rejection` | Mots confiance < 0.3 → rejetés |
| | `test_scribe_priority` | Texte Scribe priorisé sur WhisperX |
| | `test_timestamp_whisperx_priority` | Timestamp WhisperX priorisé |
| **fusion/normalizer** | `test_transcript_schema` | Schema Transcript valide |
| | `test_silence_merge` | Silences VAD+WhisperX fusionnés |
| | `test_sentence_reconstruction` | Phrases reconstruites aux silences >500ms |

### 9.2 Tests d'Intégration

| Test | Description |
|------|-------------|
| `test_real_video_short` | Vidéo de 30s → transcript complet |
| `test_real_video_with_names` | Vidéo contenant "Anthropic" → pas "anthropique" |
| `test_real_video_silences` | Vidéo avec pauses → silences détectés |
| `test_cache_hit_integration` | Même vidéo 2x → cache utilisé |
| `test_error_api_down` | API Scribe down → WhisperX+VAD seulement |

### 9.3 Validation de la Sortie

Le `transcript.json` final doit passer ces validations :

```python
def validate_transcript(transcript: Transcript) -> List[str]:
    """Valide le transcript et retourne la liste des erreurs."""
    errors = []
    
    # 1. Ordre chronologique
    for i in range(len(transcript.words) - 1):
        if transcript.words[i].start > transcript.words[i+1].start:
            error.append(f"Mots non ordonnés: {i} > {i+1}")
    
    # 2. Pas de mots dans les silences
    for mot in transcript.words:
        for silence in transcript.silences:
            if silence.start <= mot.start <= silence.end:
                errors.append(f"Mot '{mot.text}' dans un silence @ {mot.start}s")
    
    # 3. Durées cohérentes
    if transcript.words:
        dernier_mot = transcript.words[-1]
        if dernier_mot.end > transcript.duration_seconds + 1.0:
            errors.append(f"Dernier mot dépasse la durée vidéo")
    
    # 4. Speakers valides
    speaker_ids = {s.speaker_id for s in transcript.speakers}
    for word in transcript.words:
        if word.speaker_id and word.speaker_id not in speaker_ids:
            errors.append(f"Speaker inconnu: {word.speaker_id}")
    
    # 5. Confiance dans les bornes
    for word in transcript.words:
        if not (0.0 <= word.confidence <= 1.0):
            errors.append(f"Confiance hors bornes pour '{word.text}'")
    
    # 6. Silences non négatifs
    for silence in transcript.silences:
        if silence.duration_seconds < 0:
            errors.append(f"Silence négatif @ {silence.start}s")
    
    return errors
```

### 9.4 Benchmark

| Métrique | Cible | Seuil d'alerte |
|----------|-------|----------------|
| Précision mots Scribe | > 95% WER sur noms propres | < 90% |
| Précision timestamps WhisperX | ±50ms | > ±200ms |
| Précision silences VAD | ±30ms | > ±100ms |
| Temps extraction audio | < 5s (pour 10min vidéo) | > 15s |
| Temps Scribe (API) | < 30s (pour 10min audio) | > 60s |
| Temps WhisperX (CPU tiny) | < 120s (pour 5min audio) | > 300s |
| Temps VAD | < 3s (pour 10min audio) | > 10s |
| Taille sortie JSON | < 5 Mo (pour 1h audio) | > 10 Mo |

---

## 10. Pièges Connus et Solutions

### 10.1 Scribe V2 offset temporel (~200ms)

**Problème** : L'API Scribe V2 peut retourner des timestamps décalés de ~200ms par rapport à la réalité. Cela provoque un désalignement avec WhisperX.

**Solution** : L'algorithme `calculer_offset_scribe()` (section 5.3) calcule le décalage médian sur les 50 premiers mots communs et l'applique à tous les mots Scribe avant fusion.

```python
# Dans fusion/aligner.py
def align_scribe_whisperx(scribe, whisperx):
    offset = calculer_offset_scribe(scribe, whisperx)
    if abs(offset) > 0.01:  # > 10ms
        logger.info(f"Offset Scribe détecté: {offset*1000:.0f}ms → correction appliquée")
        scribe = appliquer_offset(scribe, offset)
    return scribe
```

### 10.2 WhisperX en CPU est lent

**Problème** : Le modèle WhisperX, même en `tiny`, peut prendre 5 à 10 fois le temps réel sur CPU.

**Solutions** :
- Barre de progression (`tqdm`) avec estimation du temps restant
- Logs réguliers toutes les 30s
- Mode batch (`batch_size=16` dans whisperx.transcribe) pour accélérer
- Recommandation : utiliser `tiny` pour le développement, `base` pour la prod si temps acceptable

### 10.3 Silences < 100ms = bruit de fond

**Problème** : Les micro-pauses (< 100ms) sont souvent du bruit de fond, des clics, ou des respirations, pas de vrais silences de coupe.

**Solution** : Paramètre `silence_min_ms = 100` par défaut. Tout silence en dessous de ce seuil est filtré sauf s'il est confirmé par VAD ET WhisperX.

```python
def should_keep_silence(duration_ms: float, vad_confirmed: bool, wx_confirmed: bool) -> bool:
    if duration_ms >= 500:
        return True  # Toujours garder les pauses longues
    if duration_ms >= 100 and (vad_confirmed or wx_confirmed):
        return True  # Garder si confirmé par au moins un moteur
    return False     # Filtrer
```

### 10.4 Mots fantômes WhisperX

**Problème** : Quand la confiance est basse (< 0.3), WhisperX peut "inventer" des mots qui n'existent pas dans l'audio. Cela arrive souvent sur les noms rares ou en présence de bruit.

**Solution** : Seuil `hallucination_threshold = 0.3`. Tout mot WhisperX avec confiance < 0.3 qui n'a pas de correspondance Scribe est rejeté. Le texte Scribe fait toujours foi.

```python
# Dans fusion/conflict.py
def is_likely_hallucination(word: WhisperXWord, scribe_words: list) -> bool:
    if word.confidence >= 0.3:
        return False  # Confiance suffisante
    # Vérifier si Scribe a quelque chose à cette position
    near = trouver_scribe_proche(scribe_words, word.start, seuil_ms=200)
    return near is None  # Hallucination si Scribe n'a rien
```

### 10.5 Diarization mono

**Problème** : Si la vidéo est mono (1 seule piste audio), la diarization peut ne pas fonctionner ou retourner un seul speaker.

**Solution** : En mode mono, on force `speaker_id = "SPEAKER_00"` pour tous les mots. Si WhisperX détecte plusieurs speakers malgré le mono, on conserve l'info avec un warning.

### 10.6 Conflit de langue Scribe vs WhisperX

**Problème** : Scribe et WhisperX peuvent détecter des langues différentes (ex: Scribe détecte 'fr', WhisperX détecte 'en').

**Solution** : On utilise la langue spécifiée par l'utilisateur (`--language fr`). Si non spécifiée, on prend la langue Scribe (plus fiable). On log un warning si WhisperX détecte une langue différente.

### 10.7 Fichier vidéo corrompu

**Problème** : Le fichier vidéo peut être corrompu (codec non supporté, piste audio manquante).

**Solution** : Validation en amont :
1. Vérifier que le fichier existe et est lisible
2. `ffprobe` pour vérifier la présence d'une piste audio
3. Si pas de piste audio → erreur claire : "Aucune piste audio trouvée"
4. Si codec non supporté → tentative de conversion automatique

---

## 11. Journalisation

```python
# Format des logs
LOGGING_FORMAT = "%(asctime)s  [%(levelname)s]  %(name)s  %(message)s"

# Exemple de sortie
2026-07-08 14:30:01  [INFO]   agent1_transcription.fusion.engine  Extraction audio de interview_redd.mp4...
2026-07-08 14:30:03  [INFO]   agent1_transcription.fusion.engine  Audio extrait: interview_redd_audio.wav (12.5 Mo, 734s)
2026-07-08 14:30:03  [INFO]   agent1_transcription.fusion.engine  Lancement Scribe V2, WhisperX, VAD en parallèle...
2026-07-08 14:30:03  [INFO]   agent1_transcription.scribe.client  Scribe V2: envoi fichier (12.5 Mo)...
2026-07-08 14:30:03  [INFO]   agent1_transcription.whisperx.transcribe  WhisperX tiny: transcription en cours...
2026-07-08 14:30:03  [INFO]   agent1_transcription.vad.detector  Silero VAD: détection en cours...
2026-07-08 14:30:04  [INFO]   agent1_transcription.vad.detector  VAD terminé en 0.83s (412 segments)
2026-07-08 14:30:04  [WARNING] agent1_transcription.vad.detector  Bruit de fond détecté: 23 micro-silences < 100ms filtrés
2026-07-08 14:30:08  [INFO]   agent1_transcription.scribe.client  Scribe V2: réponse reçue (8.1s, 1847 mots)
2026-07-08 14:30:08  [INFO]   agent1_transcription.scribe.cache   Scribe V2: résultat mis en cache (sha256=abc123...)
2026-07-08 14:30:21  [INFO]   agent1_transcription.whisperx.transcribe  WhisperX terminé en 18.2s (1832 mots, 156 silences)
2026-07-08 14:30:21  [INFO]   agent1_transcription.fusion.aligner  Offset Scribe détecté: +187ms → correction appliquée
2026-07-08 14:30:21  [INFO]   agent1_transcription.fusion.conflict  3 mots hallucinés WhisperX rejetés (confiance < 0.3)
2026-07-08 14:30:21  [INFO]   agent1_transcription.fusion.conflict  5 mots sans correspondance Scribe utilisés (confiance > 0.5)
2026-07-08 14:30:22  [INFO]   agent1_transcription.fusion.normalizer  Transcript: 1847 mots, 143 silences, 2 speakers
2026-07-08 14:30:22  [INFO]   agent1_transcription.main  ✓ Transcript → /output/transcript.json (45.2s total)
```

---

## 12. Dépendances (`requirements.txt`)

```txt
# Core
pydantic>=2.7.0
pydantic-settings>=2.0.0
aiohttp>=3.9.0
asyncio>=3.4.0

# Audio extraction
ffmpeg-python>=0.2.0

# WhisperX (local CPU)
whisperx>=3.1.0
torch>=2.0.0
torchaudio>=2.0.0

# VAD
silero-vad>=5.0.0

# Fusion & utils
tenacity>=8.0.0       # Retry API
tqdm>=4.64.0          # Barre de progression
numpy>=1.24.0         # Calculs alignement
scipy>=1.10.0         # Corrélation temporelle

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
pytest-cov>=4.1.0
```

---

## 13. Extension Future

### 13.1 Mode GPU

Si un GPU est disponible, WhisperX peut utiliser `cuda` au lieu de `cpu`, ce qui réduit le temps de transcription de 10x à 50x. L'architecture est déjà conçue pour supporter ce changement :

```python
# Dans config.py, ajouter :
device: str = "cpu"  # ou "cuda" si GPU disponible
compute_type: str = "float16"  # ou "float32" pour CPU
```

### 13.2 Support Multilingue

Le pipeline supporte déjà le paramètre `language`. Pour l'étendre :
- Détection automatique de la langue (Scribe retourne `language` et `language_confidence`)
- Support ISO 639-1 complet

### 13.3 Streaming

Pour les très longues vidéos (> 1h), on pourrait :
1. Découper l'audio en chunks de 10 minutes
2. Lancer Scribe/WhisperX/VAD par chunk
3. Fusionner les transcripts partiels

### 13.4 Métriques Supplémentaires

Dans `transcript.json`, ajouter :
- `words_per_second` : Débit de parole
- `silence_ratio` : Ratio silence/parole
- `speaker_turns` : Nombre de changements de locuteur

---

## 14. Contrat Agent #1 → Agent #2

L'Agent #2 (Dérushage) attend un `transcript.json` avec cette structure minimale :

```json
{
  "words": [
    {
      "text": "Anthropic",
      "start": 12.34,
      "end": 12.78,
      "confidence": 0.95,
      "speaker_id": null
    }
  ],
  "silences": [
    {
      "start": 15.00,
      "end": 15.50,
      "duration_seconds": 0.5,
      "confidence": 0.85
    }
  ],
  "sentences": [
    {
      "text": "Le premier outil, c'est d'utiliser non pas Whisper, mais plutôt ElevenLabs Scribe.",
      "start": 10.00,
      "end": 14.50,
      "words": [...],
      "speaker_id": null
    }
  ],
  "speakers": [
    {
      "speaker_id": "SPEAKER_00",
      "total_words": 1847,
      "total_duration_seconds": 120.5,
      "segment_count": 42
    }
  ],
  "duration_seconds": 734.0,
  "language": "fr"
}
```
