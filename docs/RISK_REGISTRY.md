# Registre des Risques — Pipeline de Montage Vidéo Automatisé

> **Critic & Reviewer Report** | Juillet 2025
> 12 risques identifiés, catégorisés par sévérité et priorité.

---

## 1. Risques Critiques (Blocage V1)

### R-001 : Hallucination de Timestamps par LLM

| Propriété | Valeur |
|---|---|
| **Nom** | Hallucination temporelle LLM |
| **Probabilité** | Élevée (70%) — phénomène connu des LLM |
| **Impact** | Critique — timestamps invalides → segment coupé au mauvais endroit, désync audio/vidéo |
| **Cause** | Agent #2 et #5 génèrent des timestamps via LLM sans validation |
| **Effet** | Vidéo montée avec des sauts, des空白, des boucles, ou des chevauchements |
| **Mitigation** | 1. Module `TimestampValidator` post-LLM : vérifie bornes [0, duration], ordre chronologique, non-chevauchement. 2. Référence temporelle absolue (timecode source) plutôt que relative. 3. Cross-check avec les durées réelles des segments WhisperX. |
| **Priorité** | P0 — Bloquant V1 |

### R-002 : Absence de Code/Spec pour Agents #2 et #4

| Propriété | Valeur |
|---|---|
| **Nom** | Agents manquants |
| **Probabilité** | Certaine (100%) — les fichiers n'existent pas |
| **Impact** | Critique — le pipeline ne peut pas fonctionner sans ces agents |
| **Cause** | Design incomplet : seuls #1, #3, #5 ont des specs |
| **Effet** | Pipeline inutilisable en l'état |
| **Mitigation** | 1. Créer `AGENT2_NARRATIVE_SPEC.md` avec : contrats Pydantic, prompts Jinja2, logique de dérushage (4 étapes). 2. Créer `AGENT4_AUDIO_SPEC.md` avec : contrat Epidemic Sound MCP, logique de ducking/compression, schémas. 3. Priorité absolue avant tout développement V1. |
| **Priorité** | P0 — Bloquant V1 |

### R-003 : Contrats Pydantic Divergents

| Propriété | Valeur |
|---|---|
| **Nom** | Schémas dupliqués et incohérents |
| **Probabilité** | Certaine (100%) — constaté dans l'audit |
| **Impact** | Critique — données mal interprétées entre agents, `QualityFeedback` score 0-10 vs `QaReport` score 0.0-1.0 |
| **Cause** | Pas de `shared/schemas/` centralisé |
| **Effet** | Bugs silencieux : seuil de qualité à 0.70 interprété comme 7.0/10 ou 0.70/1.0 |
| **Mitigation** | 1. Créer `shared/schemas/` avec tous les modèles. 2. Ajouter des tests de validation croisée. 3. Versionner les schémas (`schema_version`). 4. Migration immédiate de `models.py` et `schemas.py` vers `shared/`. |
| **Priorité** | P0 — Bloquant V1 |

---

## 2. Risques Techniques Élevés

### R-004 : Coût API Gemini Vision

| Propriété | Valeur |
|---|---|
| **Nom** | Explosion du budget tokens Gemini |
| **Probabilité** | Élevée (60%) — selon la durée vidéo et le nombre d'itérations |
| **Impact** | Élevé — coût potentiel de $5-50 par vidéo en mode full_video |
| **Cause** | Analyse vidéo frame par frame, 3 itérations max |
| **Effet** | Pipeline non rentable économiquement (contredit le principe "80% economy") |
| **Mitigation** | 1. Mode `keyframes` par défaut (pas `full_video`). 2. Intervalle configurable `analyze_every_n_frames` (défaut: 30). 3. Budget tracking avec alerte. 4. Cache des analyses Gemini (ne pas ré-analyser une version inchangée). 5. Option "Gemini lite" (Gemini Flash) pour les itérations > 1. |
| **Priorité** | P1 — Doit être résolu avant mise en prod |

### R-005 : Sur-dérushage par Profil Agressif

| Propriété | Valeur |
|---|---|
| **Nom** | Compression narrative excessive |
| **Probabilité** | Moyenne (40%) — dépend du profil et du contenu |
| **Impact** | Élevé — vidéo hachée, sens perdu, locuteur coupé en plein mot |
| **Cause** | Profile "aggressive" avec `compression_ratio_target: 0.55`, coupe les pauses > 400ms |
| **Effet** | Vidéo inregardable, boucle qualité ne peut pas restaurer le contenu coupé |
| **Mitigation** | 1. Détection de coupure en milieu de mot (cross-check Agent #1 timestamps). 2. Protection des segments à haute densité sémantique. 3. Seuil minimum de segment (pas de segment < 1.5s sauf si transition). 4. Review humaine obligatoire pour le profil aggressive. |
| **Priorité** | P1 — Doit être résolu avant mise en prod |

### R-006 : Désynchronisation Audio

| Propriété | Valeur |
|---|---|
| **Nom** | Audio/Video désync après montage |
| **Probabilité** | Moyenne (50%) — piège FFmpeg bien connu |
| **Impact** | Élevé — vidéo inutilisable |
| **Cause** | Mauvaise utilisation de `-ss` avant/après `-i`, concaténation de clips avec codecs audio différents, changements de framerate |
| **Effet** | Décalage audio croissant au fil de la vidéo, sync labiale perdue |
| **Mitigation** | 1. `AudioSyncGuard` déjà défini dans AGENT3 — l'utiliser systématiquement. 2. Ré-encoder l'audio en AAC 192k constant sur tous les segments. 3. Test de sync automatique après rendu (cross-corrélation audio/vidéo). 4. `-copyts` systématique. |
| **Priorité** | P1 — Doit être résolu avant mise en prod |

### R-007 : WhisperX Trop Lent sur CPU

| Propriété | Valeur |
|---|---|
| **Nom** | Performance WhisperX CPU |
| **Probabilité** | Élevée (80%) — dépend de la durée vidéo |
| **Impact** | Moyen — temps de traitement long (30min+ pour 20min de vidéo) |
| **Cause** | Modèle CPU-only, même le modèle "tiny" est lent sans GPU |
| **Effet** | Pipeline trop lent pour un usage quotidien, timeout potentiel |
| **Mitigation** | 1. Modèle "tiny" par défaut (le plus rapide). 2. Parallélisation des segments audio avant WhisperX. 3. Mode "Scribe-only" si Scribe V2 assez rapide. 4. Support GPU optionnel (NVIDIA CUDA) documenté. 5. Timeout dynamique basé sur durée vidéo × 120. |
| **Priorité** | P1 — Doit être résolu avant usage quotidien |

---

## 3. Risques Moyens

### R-008 : Pas de Cache Global

| Propriété | Valeur |
|---|---|
| **Nom** | Absence de cache inter-agent |
| **Probabilité** | Élevée (80%) — chaque itération de boucle qualité re-llamme les mêmes APIs |
| **Impact** | Moyen — coût, temps, rate limiting |
| **Cause** | Architecturé sans cache, chaque exécution est "fraîche" |
| **Effet** | Coût API 3× plus élevé que nécessaire, rate limiting OpenRouter/Gemini |
| **Mitigation** | 1. Cache Redis ou fichier basé sur hash de l'input. 2. TTL configurable. 3. Invalidation sélective. 4. Mode "cache chaud" pour les vidéos similaires. |
| **Priorité** | P2 — Optimisation critique |

### R-009 : Fallback Hyperframes → Remotion Non Testé

| Propriété | Valeur |
|---|---|
| **Nom** | Chemin de rendu alternatif non validé |
| **Probabilité** | Moyenne (50%) — Hyperframes est payant et peut être indisponible |
| **Impact** | Moyen — perte de fonctionnalités (compositions avancées) |
| **Cause** | Hyperframes requis pour les templates React avancés. Remotion est un fallback partiel. |
| **Effet** | Si Hyperframes API key absente ou API down, le rendu tombe sur FFmpeg-only qui ne supporte pas les templates |
| **Mitigation** | 1. Définir clairement le contrat `AbstractRenderer` avec méthodes `render_segment()`. 2. Implémenter `RemotionRenderer` complet (pas juste FFmpeg). 3. Test de fallback automatique. 4. Feature matrix : quelles fonctionnalités sont perdues avec chaque renderer. |
| **Priorité** | P2 — Important pour la robustesse |

### R-010 : Pas de Gestion d'Erreur API

| Propriété | Valeur |
|---|---|
| **Nom** | Résilience API insuffisante |
| **Probabilité** | Élevée (70%) — dépendances multiples : OpenRouter, Gemini, Scribe, Epidemic Sound |
| **Impact** | Moyen — pipeline bloqué si une API est down |
| **Cause** | Aucun circuit breaker, retry limité, pas de fallback documenté |
| **Effet** | Vidéo bloquée au milieu du pipeline, perte de travail |
| **Mitigation** | 1. Retry avec backoff exponentiel (3 tentatives). 2. Circuit breaker (après 5 échecs consécutifs, attendre 60s). 3. Mode dégradé documenté (ex: pas de musique si Epidemic Sound down). 4. Notification webhook sur échec critique. |
| **Priorité** | P2 — Important pour la fiabilité |

---

## 4. Risques Faibles / Nice-to-Have

### R-011 : Dashboard Streamlit Non Spécifié

| Propriété | Valeur |
|---|---|
| **Nom** | Interface utilisateur non définie |
| **Probabilité** | Certaine (100%) — pas de spec |
| **Impact** | Faible — le pipeline CLI fonctionne sans UI |
| **Cause** | Agent #6 = orchestrator + dashboard, mais seul l'orchestrator est spécifié |
| **Effet** | Pas de suivi visuel des vidéos en cours |
| **Mitigation** | 1. Définir les vues du dashboard (jobs en cours, historique, validation humaine). 2. Utiliser WebSocket pour mise à jour temps réel. 3. Priorité post-V1. |
| **Priorité** | P3 — Nice-to-have V1 |

### R-012 : Pas de Support Multilingue

| Propriété | Valeur |
|---|---|
| **Nom** | Français uniquement |
| **Probabilité** | Certaine (100%) — `language: "fr"` en dur |
| **Impact** | Faible — couvre le besoin initial |
| **Cause** | Target = vidéos françaises, Scribe V2 configuré en fr |
| **Effet** | Impossible de traiter des vidéos en anglais ou autres langues |
| **Mitigation** | 1. Rendre la langue paramétrable dans les profils. 2. Détection automatique de langue via WhisperX. 3. Adapter les prompts LLM pour la langue détectée. |
| **Priorité** | P3 — Nice-to-have |

---

## Heatmap Synthétique

```
Priorité P0 (Bloquant)    ████████████████████  3 risques
Priorité P1 (Critique)    ████████████████      4 risques  
Priorité P2 (Important)   ██████████            3 risques
Priorité P3 (Nice-to-have)████                  2 risques
```

| Priorité | Nb | Risques |
|---|---|---|
| **P0** | 3 | R-001, R-002, R-003 |
| **P1** | 4 | R-004, R-005, R-006, R-007 |
| **P2** | 3 | R-008, R-009, R-010 |
| **P3** | 2 | R-011, R-012 |

---
