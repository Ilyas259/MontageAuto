# Revue de Cohérence — Pipeline de Montage Vidéo Automatisé

> **Critic & Reviewer Report** | Juillet 2025
> Objectif : Vérifier la cohérence inter-agents, les contrats de données, la couverture des concepts vidéo.

---

## 1. Tableau de Couverture des Concepts Vidéo

La vision source (vidéo fondatrice) mentionne les concepts suivants. Voici leur couverture dans la conception :

| # | Concept vidéo source | Couvert ? | Où ? | GAP |
|---|---|---|---|---|
| 1 | **97% d'automatisation** | ✅ Couvert | README, ARCHITECTURE | OK |
| 2 | **80% de qualité suffisante** | ✅ Couvert | Architecture (principe fondateur) | OK — mais seuils 0.70-0.95 dans Agent #5, pas de "80%" explicite |
| 3 | **Boucle qualité Gemini → feedback LLM** | ✅ Couvert | Agent #5 spec complète | OK |
| 4 | **Gemini décisionnel prépondérant** | ✅ Couvert | AGENT5_QUALITY_SPEC.md §1 | OK — bien documenté |
| 5 | **Vérification humaine finale obligatoire** | ✅ Couvert | Agent #6, schéma `HumanApproval` | OK |
| 6 | **Hyperframes pour rendu vidéo** | ✅ Couvert | AGENT3_MONTAGE_SPEC.md §4-5 | ⚠️ Implémentation partielle (fallback Remotion) |
| 7 | **Epidemic Sound MCP pour audio** | ✅ Couvert | Agent #4 dans ARCHITECTURE | ⚠️ Spec Agent #4 absente |
| 8 | **Montage narratif (dérushage sémantique)** | ✅ Couvert | Agent #2 dans ARCHITECTURE | ⚠️ Spec Agent #2 absente |
| 9 | **B-rolls automatiques** | ✅ Couvert | AGENT3_MONTAGE_SPEC.md §7 | OK |
| 10 | **Sous-titres karaoke mot-à-mot** | ✅ Couvert | AGENT3_MONTAGE_SPEC.md §8 | OK |
| 11 | **Transitions et motion design** | ✅ Couvert | AGENT3_MONTAGE_SPEC.md §6 | OK |
| 12 | **Sync audio guard (anti-désync)** | ✅ Couvert | AGENT3_MONTAGE_SPEC.md §9.3 | OK |
| 13 | **Cache API (éviter re-appels)** | ⚠️ Partiel | Mentionné dans AGENT1 (Scribe cache) | ❌ Pas de stratégie de cache globale |
| 14 | **Fallback WhisperX si Scribe indisponible** | ✅ Couvert | AGENT1 | OK |
| 15 | **WhisperX lent en CPU → modèle tiny** | ⚠️ Partiel | AGENT1 (modèle tiny) | ⚠️ Précision insuffisante pour montage pro |
| 16 | **Sur-dérushage si trop agressif** | ✅ Couvert | Profils aggressive/natural | OK |
| 17 | **Hallucination de timestamps LLM** | ❌ Non couvert | Aucune spec | ❌ **GAP critique** |
| 18 | **Coût tokens Gemini Vision** | ⚠️ Partiel | Mentionné dans AGENT5 (3 modes d'analyse) | Pas de budget tracking |
| 19 | **3% de doute résiduel → vérif humaine** | ✅ Couvert | README, ARCHITECTURE | OK |

---

## 2. Matrice de Cohérence Inter-Agents

### 2.1 Qui produit quoi, qui consomme quoi

| Agent | Produit (Sortie) | Consommé par | Fichier | Contrat Pydantic |
|---|---|---|---|---|
| **#1 Transcription** | `transcript.json` | Agent #2 | `/data/transcriptions/` | `Transcript` (AGENT1 spec §4.5) |
| **#2 Narrative** | `cutlist.json` | Agent #3 | `/data/cutlists/` | `CutList` (DATA_CONTRACTS, AGENT3 models) |
| **#2 Narrative** | `script_nettoye.json` | Agent #3 | `/data/cutlists/` | `CleanScript` (DATA_CONTRACTS) |
| **#2 Narrative** | `broll_suggestions.json` | Agent #3 | `/data/cutlists/` | `BRollSuggestions` (DATA_CONTRACTS) |
| **#3 Montage** | `edit_metadata.json` | Agent #4 | `/data/renders/` | `EditMetadata` (DATA_CONTRACTS) |
| **#3 Montage** | Vidéo rendue (MP4) | Agent #4 | `/data/renders/` | N/A (fichier binaire) |
| **#4 Audio** | Vidéo + audio mixée | Agent #5 | `/data/audio/` | `AudioMetadata` (DATA_CONTRACTS) |
| **#5 Qualité** | `qa_report.json` | Agent #6 | `/data/qa/` | `QaReport` (DATA_CONTRACTS) |
| **#5 Qualité** | `feedback.json` | Agent #3, #2, #4 | `/data/qa/` | `FeedbackInstructions` (DATA_CONTRACTS) |
| **#6 Humain** | `approval.json` | Archive | `/data/final/` | `HumanApproval` (DATA_CONTRACTS) |

### 2.2 Problèmes de Cohérence Identifiés

#### 🔴 CRITIQUE : Contrats dupliqués et divergents

Trois sources définissent des schémas pour les mêmes concepts, sans synchronisation :

| Concept | DATA_CONTRACTS.md | src/agent3_montage/models.py | specs agents |
|---|---|---|---|
| **BrollPlacement** | `broll_suggestions` tableau | `BrollPlacement` avec `placement: Literal["overlay","fullscreen","split"]` | Cohérent ✅ |
| **CutSegment** | `segments: list[dict]` non typé | `CutSegment` avec `type Literal` + `transition_out: Literal` | ❌ DATA_CONTRACTS sous-typé |
| **Feedback/QaReport** | `QaReport` avec `overall_score: float` (0-1) | `QualityFeedback` avec `overall_score: float` (0-10) | ❌ **Échelles différentes !** |
| **QualityIssue** | `metric: list[MetricScore]` | `QualityIssue` avec `severity: Literal` | ❌ Structures différentes |

**🔧 Solution** : Centraliser tous les schémas dans `shared/schemas/` et les importer par tous les agents. Supprimer les définitions redondantes.

#### 🔴 CRITIQUE : Agent #2 et #4 sans spécifications

- **Agent #2** (Analyse Narrative & Dérushage) : Mentionné comme existant (brief utilisateur : `narrative_analyzer/` complet avec Dockerfile, config, prompts Jinja2, schémas Pydantic, 4 étapes) mais **aucun fichier de spec** dans `docs/` et **aucun code** sous `agents/agent-2-narrative/`.
- **Agent #4** (Design Audio) : Aucune spec, aucun code. Epidemic Sound MCP mentionné mais pas d'interface définie.

**🔧 Solution** : Créer `AGENT2_NARRATIVE_SPEC.md` et `AGENT4_AUDIO_SPEC.md` au même niveau de détail que les autres specs, avec contrats Pydantic complets.

#### 🟡 MOYEN : DATA_CONTRACTS.md déconnecté de l'implémentation

Le fichier DATA_CONTRACTS.md décrit 6 contrats (TranscriptOutput → HumanApproval) mais :
- `TranscriptOutput` utilise `segments: list[dict]` (non typé) au lieu de `list[Sentence]`
- L'orchestrator interne définit `PipelineState` et `PipelineEvent` jamais utilisés ailleurs
- Le schéma `EditMetadata` n'est pas implémenté dans `models.py` du Agent #3

**🔧 Solution** : Mettre à jour DATA_CONTRACTS.md pour refléter les schémas réels d'`src/agent3_montage/models.py`, ou vice-versa.

#### 🟡 MOYEN : Boucle qualité — flux de feedback ambigu

La boucle qualité (Agent #5 → Agent #3, #2, #4) est décrite mais le mécanisme exact de ré-injection est flou :
- L'Orchestrator (Agent #6) doit-il intercepter le feedback et redéclencher les bons agents ?
- Qui gère le compteur d'itérations (3 max) ?
- Le feedback peut-il cibler Agent #1 (retranscription) ou seulement #3, #2, #4 ?

**🔧 Solution** : Définir un sous-protocole clair : `CorrectionRequest` → `Agent #6` (Orchestrator) → dispatch. Ajouter un champ `iteration_scope` dans le feedback.

#### 🟢 FAIBLE : Chemins de données incohérents entre docs

| Document | Chemin Agent #3 → Agent #4 | Chemin Agent #5 |
|---|---|---|
| DEPLOYMENT.md docker-compose | `--output /data/renders` → `--input /data/renders` | `--video /data/audio` |
| ARCHITECTURE.md | `/data/renders/` | `/data/qa/` |
| DATA_CONTRACTS.md | `edit_metadata.json` dans renders | `qa_report.json` dans qa |

Le docker-compose de Agent #5 lit `--video /data/audio` mais la spec Agent #5 attend `video_path: str` — cohérent mais le nommage "audio" pour une vidéo est trompeur. Agent #4 lit `--metadata /data/cutlists` (sortie Agent #2) mais Agent #3 produit `edit_metadata.json` dans `/data/renders`. **Incohérence : Agent #4 lit deux dossiers différents pour ses métadonnées.**

**🔧 Solution** : Uniformiser : Agent #4 lit `--input /data/renders/render_*.mp4` + `--metadata /data/renders/edit_metadata.json`.

---

## 3. Gaps Identifiés et Solutions Proposées

### Gap #1 — Pas de mécanisme anti-hallucination de timestamps
**Sévérité** : 🔴 Critique  
**Description** : Les LLM (Agent #2, Agent #5) peuvent halluciner des timestamps qui ne correspondent pas à la réalité. Aucune validation croisée n'est prévue.  
**Solution** : Ajouter un module `TimestampValidator` qui vérifie que les timestamps produits par LLM sont dans les bornes de la vidéo source, qu'ils respectent l'ordre chronologique, et qu'ils ne dépassent pas la durée totale.

### Gap #2 — Pas de gestion des erreurs API dégradées
**Sévérité** : 🔴 Critique  
**Description** : Si Scribe V2 API est down, WhisperX prend le relais. Mais si OpenRouter est down pour Agent #2, ou Gemini pour Agent #5, ou Epidemic Sound pour Agent #4 — aucun fallback documenté.  
**Solution** : Ajouter un `ResilienceLayer` avec retry exponentiel, circuit breaker, et fallback (e.g., mode "dégradé" si Gemini indisponible → analyse textuelle uniquement).

### Gap #3 — Pas de shared/ (code partagé)
**Sévérité** : 🔴 Critique  
**Description** : L'ARCHITECTURE.md décrit `shared/schemas/`, `shared/utils/`, `shared/config/` mais ces dossiers n'existent pas dans le code. Chaque agent duplique ses schémas.  
**Solution** : Créer `shared/` immédiatement, y déplacer tous les contrats Pydantic communs, et référencer ce package depuis chaque agent.

### Gap #4 — Pas de stratégie de cache globale
**Sévérité** : 🟡 Moyen  
**Description** : Seul Agent #1 mentionne un cache (Scribe cache local). Pas de cache pour les appels LLM (OpenRouter), Gemini Vision, ou les assets B-roll. Coût API potentiellement explosif.  
**Solution** : Implémenter un `CacheManager` basé sur hash de contenu + Redis ou fichier, avec TTL configurable. Appliquer à tous les appels API externes.

### Gap #5 — Agent #4 (Audio) non spécifié
**Sévérité** : 🔴 Critique  
**Description** : Epidemic Sound MCP est une API externe dont le contrat exact (recherche musique, téléchargement, licensing) n'est pas documenté. Le ducking, la compression, le mixage ne sont pas spécifiés.  
**Solution** : Rédiger `AGENT4_AUDIO_SPEC.md` avec schémas Pydantic, logique de ducking, et contrat Epidemic Sound MCP.

### Gap #6 — Pas de tests d'intégration inter-agents
**Sévérité** : 🟡 Moyen  
**Description** : Chaque agent a des tests unitaires prévus, mais aucun test qui vérifie le flux complet Agent #1 → #2 → #3 → #4 → #5 → #6 avec des fixtures réalistes.  
**Solution** : Ajouter un test d'intégration E2E dans `tests/test_pipeline_integration.py` qui utilise des fichiers mock pour chaque étape.

### Gap #7 — Pas de gestion des timeouts par étape
**Sévérité** : 🟡 Moyen  
**Description** : Un timeout global de 3600s par agent est défini. Mais WhisperX sur CPU peut prendre 30min pour une vidéo de 20min (modèle tiny). Le timeout peut expirer prématurément.  
**Solution** : Timeouts dynamiques basés sur la durée vidéo : `timeout = max(3600, duration * 120)` secondes.

### Gap #8 — Dashboard Streamlit non spécifié
**Sévérité** : 🟢 Faible  
**Description** : Agent #6 inclut un dashboard Streamlit (port 8501) mais aucune spec sur son fonctionnement : affichage en temps réel ? historique ? upload ?  
**Solution** : Ajouter une section dans AGENT6_ORCHESTRATOR_SPEC.md décrivant le dashboard.

### Gap #9 — Pas de mécanisme de rollback
**Sévérité** : 🟡 Moyen  
**Description** : La boucle qualité prévoit un rollback si le score dérive négativement (score < initial * 0.8), mais le mécanisme n'est pas documenté : qui conserve la version précédente ? où ?  
**Solution** : Ajouter `best_version.mp4` dans `/data/qa/` mis à jour à chaque itération. L'Orchestrator restore cette version en cas de dérive.

### Gap #10 — Formats vidéo d'entrée restrictifs
**Sévérité** : 🟢 Faible  
**Description** : Agent #1 n'accepte que MP4/MOV. Pas de support pour MKV, AVI, WebM, ou URL YouTube.  
**Solution** : Ajouter un module `VideoIngestion` avec FFmpeg générique + détection automatique de format + téléchargement YouTube-dl optionnel.

---

## 4. Résumé des Écarts de Couverture Vidéo

| Métrique | Valeur |
|---|---|
| Concepts vidéo couverts | 17/19 (89%) |
| Agents avec spec complète | 3/5 (60%) — #1, #3, #5 |
| Agents sans spec | 2/5 (40%) — #2, #4 |
| Orchestrator sans spec | 1/1 (100%) — #6 |
| Contrats Pydantic unifiés | ❌ Non (3 définitions divergentes) |
| Code source implémenté | Agent #3 (complet), Agent #5 (schemas.py) |
| Tests d'intégration | ❌ Non |

---
