# Fonctionnalités Manquantes & Roadmap V1

> **Basé sur le rapport Critic (REVIEW.md) et le registre des risques (RISK_REGISTRY.md)**  
> Juillet 2025

---

## 🚨 P0 — Bloquant avant toute implémentation

### MF-001 : Schémas Pydantic centralisés

**Problème** : 3 sources définissent des schémas pour les mêmes concepts avec des divergences (QualityFeedback score 0-10 vs QaReport score 0.0-1.0).

**Solution** :
- Créer `shared/schemas/` à la racine du projet
- Tous les agents importent depuis ce dossier central
- Ajouter `schema_version` dans chaque modèle
- Tests de validation croisée obligatoires

**Fichier cible** : `shared/schemas/__init__.py` + `shared/schemas/transcript.py`, `cutlist.py`, `audio.py`, `qa.py`

---

### MF-002 : Validation des timestamps LLM

**Problème** : Agents #2 et #5 génèrent des timestamps via LLM sans validation — risque d'hallucination temporelle (R-001).

**Solution** : Module `TimestampValidator` post-LLM qui :
1. Vérifie les bornes `[0, source_duration]`
2. Vérifie l'ordre chronologique (`start < end`)
3. Vérifie le non-chevauchement avec les segments existants
4. Cross-check avec les timestamps réels du transcript WhisperX
5. Rejette les timestamps dont la différence avec le mot le plus proche > 0.5s

**Fichier cible** : `shared/validators/timestamp_validator.py`

---

### MF-003 : Cache API global

**Problème** : Pas de stratégie de cache pour les appels API (OpenRouter, Gemini, Scribe). Chaque run re-appelle les mêmes services.

**Solution** :
- Cache Redis (optionnel) ou SQLite local
- Cache des résultats de transcription (hash du fichier audio)
- Cache des analyses LLM (hash du transcript + hash du prompt)
- Cache des analyses Gemini (hash de la vidéo + hash du seuil de qualité)
- TTL configurable par type de cache (1h pour transcription, 7j pour analyse LLM)

**Fichier cible** : `shared/cache/`

---

## 🟡 P1 — Avant mise en production

### MF-004 : Budget tracking API

**Problème** : Pas de tracking des coûts API (Gemini Vision peut coûter $5-50/vidéo).

**Solution** :
- Logger les tokens consommés par chaque appel
- Estimer le coût en $ par vidéo
- Seuil d'alerte configurable (ex: $2/vidéo → warning)
- Dashboard optionnel

**Fichier cible** : `shared/monitoring/budget_tracker.py`

---

### MF-005 : Optimisation WhisperX CPU

**Problème** : WhisperX avec modèle `tiny` est rapide mais imprécis pour le montage pro. Les modèles plus gros (`small`, `medium`) sont lents sur CPU.

**Solution** :
- Détection auto du hardware (CPU vs GPU vs NPU)
- Sur CPU : `tiny` pour le batch processing, `base` pour le VAD refinement
- Option utilisateur : `whisper_model: "base"` dans config
- Fallback : `faster-whisper` si `whisperx` trop lent

**Fichier cible** : `agents/agent1-transcription/src/whisper_adapter.py`

---

### MF-006 : Gestion des erreurs pipeline

**Problème** : Pas de middleware d'erreur global. Si un agent échoue, le pipeline peut continuer avec des données invalides.

**Solution** :
- `PipelineError` centralisé avec code d'erreur, agent source, et cause
- Mode `fail_fast` (arrêt au premier échec) vs `degraded` (continuer avec les données partielles)
- Notifications webhook en cas d'échec
- Retry automatique configurable (3 tentatives par défaut)

**Fichier cible** : `shared/errors/`

---

## 🟢 P2 — Améliorations futures

### MF-007 : Dashboard de monitoring

**Solution** : Interface Streamlit ou Grafana pour visualiser :
- État actuel du pipeline (en cours, terminé, échoué)
- Métriques de qualité (compression_ratio, scores Gemini)
- Coûts API cumulés
- Historique des runs

---

### MF-008 : Mode batch multi-vidéos

**Solution** : File d'attente avec processing parallèle de N vidéos.
- Queue Redis (RQ / Celery)
- Limite configurable de workers simultanés
- Notification à la fin de chaque vidéo

---

### MF-009 : Versioning des schémas

**Solution** : `schema_version` dans chaque modèle Pydantic + migration automatique.
- V1 → V2 : ajout du champ `b_roll_suggestions` dans CutList
- Validation backward-compatible

---

## Tableau de synthèse

| ID | Fonctionnalité | Priorité | Effort estimé | Dépendance |
|----|---------------|----------|---------------|------------|
| MF-001 | Schémas centralisés | P0 | 2 jours | Aucune |
| MF-002 | Validation timestamps | P0 | 1 jour | MF-001 |
| MF-003 | Cache API global | P0 | 3 jours | Aucune |
| MF-004 | Budget tracking | P1 | 1 jour | MF-003 |
| MF-005 | Optimisation WhisperX | P1 | 2 jours | Agent #1 |
| MF-006 | Gestion d'erreurs pipeline | P1 | 2 jours | Architecture |
| MF-007 | Dashboard monitoring | P2 | 5 jours | Tous agents |
| MF-008 | Mode batch multi-vidéos | P2 | 5 jours | Pipeline |
| MF-009 | Versioning schémas | P2 | 1 jour | MF-001 |
