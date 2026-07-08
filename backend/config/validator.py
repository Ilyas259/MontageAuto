"""Validateur de configuration — utilise Pydantic pour valider les entrées."""

from typing import Any

from backend.config.schemas import ValidationError, ValidationResult


class ConfigValidator:
    """Valide une configuration d'agent ou de pipeline."""

    def validate_agent_params(
        self, agent_id: str, params: dict[str, Any]
    ) -> ValidationResult:
        """Valide les paramètres d'un agent selon son schéma."""
        result = ValidationResult()
        schema = self._get_agent_schema(agent_id)

        for field_name, field_schema in schema.get("properties", {}).items():
            if field_name not in params:
                if field_schema.get("required", False):
                    result.errors.append(
                        ValidationError(
                            field=field_name,
                            message=f"Champ obligatoire manquant : {field_name}",
                            expected="présent",
                        )
                    )
                continue

            value = params[field_name]
            expected_type = field_schema.get("type", "string")

            if not self._check_type(value, expected_type):
                result.errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Type invalide pour {field_name}: attendu {expected_type}, reçu {type(value).__name__}",
                        value=value,
                        expected=expected_type,
                    )
                )

            # Vérification des enum
            if "enum" in field_schema and value not in field_schema["enum"]:
                result.errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Valeur invalide pour {field_name}: '{value}'",
                        value=value,
                        expected=f"un de {field_schema['enum']}",
                    )
                )

            # Vérification min/max
            if isinstance(value, (int, float)):
                if "minimum" in field_schema and value < field_schema["minimum"]:
                    result.warnings.append(
                        f"{field_name}: {value} < minimum {field_schema['minimum']}"
                    )
                if "maximum" in field_schema and value > field_schema["maximum"]:
                    result.warnings.append(
                        f"{field_name}: {value} > maximum {field_schema['maximum']}"
                    )

        result.valid = len(result.errors) == 0
        return result

    def _get_agent_schema(self, agent_id: str) -> dict:
        """Retourne le JSON Schema pour un agent avec paramètres détaillés."""

        # ─── Champs communs à tous les agents ───────────────────────
        mode_field = {
            "type": "string",
            "enum": ["api", "local", "auto"],
            "default": "auto",
            "description": "Mode d'exécution: api=cloud, local=sans API, auto=hérité du pipeline",
        }
        api_key_field = {
            "type": "string",
            "default": "",
            "description": "Clé API pour le service (requis en mode api)",
            "writeOnly": True,
        }

        schemas = {
            "transcription": {
                "type": "object",
                "title": "Transcription",
                "description": "Transcription audio/vidéo avec WhisperX ou Scribe V2",
                "properties": {
                    # ── Modèle
                    "model_size": {
                        "type": "string",
                        "enum": ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"],
                        "default": "large-v3",
                        "description": "Taille du modèle Whisper (large-v3 = max précision)",
                    },
                    "language": {
                        "type": "string",
                        "default": "fr",
                        "description": "Code langue ISO (fr, en, es, de, etc.)",
                    },
                    "temperature": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.0,
                        "description": "Température d'échantillonnage (0 = déterministe, 1 = créatif)",
                    },
                    "beam_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5,
                        "description": "Taille du faisceau de recherche (beam search)",
                    },
                    "best_of": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                        "description": "Nombre d'hypothèses à évaluer",
                    },

                    # ── VAD (Voice Activity Detection)
                    "vad_mode": {
                        "type": "string",
                        "enum": ["relaxed", "balanced", "aggressive"],
                        "default": "balanced",
                        "description": "Agressivité de la détection de parole (aggressive = coupe les silences courts)",
                    },
                    "vad_sensitivity": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5,
                        "description": "Sensibilité de la VAD (0 = détecte tout, 1 = ne détecte que la parole forte)",
                    },
                    "min_silence_duration": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 10.0,
                        "default": 0.5,
                        "description": "Durée minimale de silence (secondes) pour couper",
                    },
                    "no_speech_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.6,
                        "description": "Seuil de confiance 'pas de parole' (plus bas = moins de faux positifs)",
                    },
                    "compression_ratio_threshold": {
                        "type": "number",
                        "minimum": 1.0,
                        "maximum": 3.0,
                        "default": 2.4,
                        "description": "Seuil de ratio de compression pour le texte",
                    },

                    # ── Sous-titres & timestamps
                    "word_timestamps": {
                        "type": "boolean",
                        "default": True,
                        "description": "Inclure les timestamps mot par mot",
                    },
                    "highlight_words": {
                        "type": "boolean",
                        "default": True,
                        "description": "Surligner les mots prononcés en temps réel",
                    },
                    "max_line_width": {
                        "type": "integer",
                        "minimum": 20,
                        "maximum": 100,
                        "default": 42,
                        "description": "Nombre max de caractères par ligne de sous-titre",
                    },
                    "max_line_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                        "default": 2,
                        "description": "Nombre max de lignes par sous-titre",
                    },

                    # ── Aide à la transcription
                    "initial_prompt": {
                        "type": "string",
                        "default": "",
                        "description": "Texte d'amorçage pour guider la transcription (ex: vocabulaire technique)",
                    },
                    "hotwords": {
                        "type": "string",
                        "default": "",
                        "description": "Mots-clés séparés par des espaces à reconnaître (noms propres, jargon)",
                    },
                    "condition_on_previous_text": {
                        "type": "boolean",
                        "default": True,
                        "description": "Conditionner la prédiction sur le texte précédent",
                    },

                    # ── Performance
                    "batch_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 64,
                        "default": 8,
                        "description": "Taille de lot pour le traitement GPU (augmenter = plus rapide, plus de VRAM)",
                    },
                    "compute_type": {
                        "type": "string",
                        "enum": ["auto", "float16", "int8", "int4"],
                        "default": "auto",
                        "description": "Type de calcul (int8 = plus rapide, moins précis)",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },

            "derushage": {
                "type": "object",
                "title": "Dérushage Narratif",
                "description": "Analyse LLM du transcript, génération cut_list et script nettoyé",
                "properties": {
                    # ── LLM
                    "model": {
                        "type": "string",
                        "default": "deepseek",
                        "description": "Modèle LLM à utiliser (deepseek, granite, gpt4, etc.)",
                    },
                    "temperature": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.3,
                        "description": "Créativité du LLM (0 = strict, 1 = créatif)",
                    },
                    "top_p": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.9,
                        "description": "Nucleus sampling — filtre les tokens les moins probables",
                    },
                    "max_output_tokens": {
                        "type": "integer",
                        "minimum": 256,
                        "maximum": 8192,
                        "default": 2048,
                        "description": "Nombre max de tokens dans la réponse LLM",
                    },
                    "context_window": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 100000,
                        "default": 16000,
                        "description": "Taille du contexte (caractères) envoyée au LLM à chaque étape",
                    },

                    # ── Découpage
                    "max_cut_duration": {
                        "type": "number",
                        "minimum": 5,
                        "maximum": 300,
                        "default": 60,
                        "description": "Durée maximale d'un plan (secondes)",
                    },
                    "min_sentence_duration": {
                        "type": "number",
                        "minimum": 0.5,
                        "maximum": 30,
                        "default": 2.0,
                        "description": "Durée minimale d'une phrase gardée (secondes)",
                    },
                    "keep_filler_words": {
                        "type": "boolean",
                        "default": False,
                        "description": "Conserver les mots de remplissage (euh, ben, du coup…)",
                    },
                    "remove_uhs_and_ums": {
                        "type": "boolean",
                        "default": True,
                        "description": "Supprimer les hésitations (euh, hum, ah)",
                    },
                    "preserve_questions": {
                        "type": "boolean",
                        "default": True,
                        "description": "Conserver les questions posées par l'interviewer",
                    },

                    # ── Style d'édition
                    "summary_style": {
                        "type": "string",
                        "enum": ["natural", "concise", "detailed", "bullet"],
                        "default": "natural",
                        "description": "Style du script nettoyé (natural = conversationnel, bullet = liste à puces)",
                    },
                    "highlight_best_moments": {
                        "type": "boolean",
                        "default": True,
                        "description": "Identifier et marquer les meilleurs moments (pour teasers)",
                    },

                    # ── Prompting
                    "system_prompt": {
                        "type": "string",
                        "default": "Tu es un monteur vidéo expert. Analyse le transcript et génère une cut_list optimisée.",
                        "description": "Instruction système pour le LLM",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },

            "montage": {
                "type": "object",
                "title": "Montage Vidéo",
                "description": "Assemblage final avec rendu, sous-titres, transitions et B-rolls",
                "properties": {
                    # ── Moteur de rendu
                    "renderer": {
                        "type": "string",
                        "enum": ["hyperframes", "remotion", "ffmpeg"],
                        "default": "hyperframes",
                        "description": "Moteur de rendu: hyperframes=cloud pro, remotion=React local, ffmpeg=basique",
                    },

                    # ── Format de sortie
                    "resolution": {
                        "type": "string",
                        "enum": ["720p", "1080p", "1440p", "4k"],
                        "default": "1080p",
                        "description": "Résolution de la vidéo finale",
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["16:9", "9:16", "1:1", "4:5"],
                        "default": "16:9",
                        "description": "Ratio d'image (16:9 = paysage, 9:16 = TikTok/Reels)",
                    },
                    "fps": {
                        "type": "integer",
                        "enum": [24, 25, 30, 48, 60],
                        "default": 30,
                        "description": "Images par seconde (24 = cinéma, 30 = standard, 60 = sport)",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["mp4", "mov", "webm", "gif"],
                        "default": "mp4",
                        "description": "Format de sortie",
                    },
                    "bitrate": {
                        "type": "string",
                        "enum": ["auto", "1M", "5M", "10M", "20M", "50M"],
                        "default": "auto",
                        "description": "Débit binaire vidéo (auto = laisse le renderer décider)",
                    },
                    "codec": {
                        "type": "string",
                        "enum": ["h264", "h265", "vp9", "av1"],
                        "default": "h264",
                        "description": "Codec vidéo (h264 = max compatibilité, av1 = meilleure compression)",
                    },

                    # ── Sous-titres
                    "subtitles_enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Incruster les sous-titres dans la vidéo",
                    },
                    "subtitle_style": {
                        "type": "string",
                        "enum": ["classic", "modern", "minimal", "animated"],
                        "default": "modern",
                        "description": "Style visuel des sous-titres",
                    },
                    "subtitle_font_size": {
                        "type": "integer",
                        "minimum": 12,
                        "maximum": 72,
                        "default": 24,
                        "description": "Taille de police des sous-titres (px)",
                    },
                    "subtitle_position": {
                        "type": "string",
                        "enum": ["bottom", "top", "auto"],
                        "default": "bottom",
                        "description": "Position des sous-titres à l'écran",
                    },
                    "subtitle_color": {
                        "type": "string",
                        "default": "#FFFFFF",
                        "description": "Couleur hex des sous-titres (ex: #FFFFFF)",
                    },
                    "subtitle_background": {
                        "type": "string",
                        "enum": ["none", "shadow", "outline", "solid"],
                        "default": "shadow",
                        "description": "Fond des sous-titres pour lisibilité",
                    },

                    # ── Transitions
                    "transition_style": {
                        "type": "string",
                        "enum": ["cut", "fade", "dissolve", "slide", "zoom", "wipe"],
                        "default": "cut",
                        "description": "Style de transition entre les plans",
                    },
                    "transition_duration": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 2.0,
                        "default": 0.3,
                        "description": "Durée des transitions (secondes)",
                    },

                    # ── B-roll
                    "broll_enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Ajouter des images de coupe automatiques",
                    },
                    "broll_source": {
                        "type": "string",
                        "enum": ["auto", "local", "pexels", "pixabay", "none"],
                        "default": "auto",
                        "description": "Source des B-rolls (auto = cherche mieux adapté)",
                    },
                    "broll_count_per_minute": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10,
                        "default": 2,
                        "description": "Nombre de B-rolls par minute de vidéo",
                    },

                    # ── Effets visuels
                    "color_grade": {
                        "type": "string",
                        "enum": ["none", "warm", "cool", "vintage", "cinematic", "muted"],
                        "default": "none",
                        "description": "Étalonnage couleur (cinematic = look cinéma)",
                    },
                    "enable_ken_burns": {
                        "type": "boolean",
                        "default": False,
                        "description": "Effet Ken Burns (zoom doux sur les images fixes)",
                    },
                    "background_blur": {
                        "type": "boolean",
                        "default": False,
                        "description": "Flou artistique en arrière-plan",
                    },
                    "speed_control": {
                        "type": "string",
                        "enum": ["auto", "manual", "none"],
                        "default": "auto",
                        "description": "Ajustement automatique de la vitesse des séquences",
                    },

                    # ── Intro/Outro
                    "intro_enabled": {
                        "type": "boolean",
                        "default": False,
                        "description": "Ajouter une intro animée",
                    },
                    "intro_duration": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3,
                        "description": "Durée de l'intro (secondes)",
                    },
                    "outro_enabled": {
                        "type": "boolean",
                        "default": False,
                        "description": "Ajouter un outro (CTA, logo, etc.)",
                    },
                    "outro_duration": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3,
                        "description": "Durée de l'outro (secondes)",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },

            "audio": {
                "type": "object",
                "title": "Design Audio",
                "description": "Musique, effets sonores, voix-off et mixage audio",
                "properties": {
                    # ── Musique
                    "music_enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Ajouter une musique de fond",
                    },
                    "music_genre": {
                        "type": "string",
                        "enum": ["auto", "cinematic", "ambient", "upbeat", "corporate", "electronic", "lo-fi", "rock", "jazz"],
                        "default": "auto",
                        "description": "Genre musical (auto = adapté au contenu)",
                    },
                    "music_mood": {
                        "type": "string",
                        "enum": ["auto", "epic", "calm", "dramatic", "funny", "inspiring", "sad", "suspense"],
                        "default": "auto",
                        "description": "Ambiance musicale",
                    },
                    "music_volume": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.15,
                        "description": "Volume de la musique (0 = muet, 1 = pleine puissance)",
                    },
                    "music_fade_duration": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 5.0,
                        "default": 1.0,
                        "description": "Durée du fondu enchaîné musical (secondes)",
                    },

                    # ── Ducking (réduction auto du volume musique quand quelqu'un parle)
                    "ducking_enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Baisser la musique quand quelqu'un parle",
                    },
                    "ducking_level": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.3,
                        "description": "Réduction du volume musique pendant la parole (0 = pas de réduc, 1 = muet)",
                    },
                    "ducking_attack": {
                        "type": "number",
                        "minimum": 0.01,
                        "maximum": 1.0,
                        "default": 0.1,
                        "description": "Rapidité de la baisse de volume (secondes)",
                    },
                    "ducking_release": {
                        "type": "number",
                        "minimum": 0.05,
                        "maximum": 2.0,
                        "default": 0.5,
                        "description": "Temps de remontée du volume après la parole (secondes)",
                    },

                    # ── Effets sonores
                    "sfx_enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Ajouter des effets sonores automatiques",
                    },
                    "sfx_volume": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5,
                        "description": "Volume des effets sonores",
                    },
                    "sfx_categories": {
                        "type": "string",
                        "default": "transitions,emphasis,ambient",
                        "description": "Catégories d'effets (transitions, emphasis, ambient, UI) séparées par virgule",
                    },

                    # ── Voix-off / Narration
                    "voiceover_enabled": {
                        "type": "boolean",
                        "default": False,
                        "description": "Ajouter une voix-off (ElevenLabs ou TTS local)",
                    },
                    "voiceover_language": {
                        "type": "string",
                        "default": "fr",
                        "description": "Langue de la voix-off",
                    },
                    "voiceover_voice": {
                        "type": "string",
                        "default": "",
                        "description": "ID de la voix ElevenLabs (laisser vide = voix par défaut)",
                    },
                    "voiceover_speed": {
                        "type": "number",
                        "minimum": 0.5,
                        "maximum": 2.0,
                        "default": 1.0,
                        "description": "Vitesse de la voix-off (0.5 = ralenti, 2.0 = accéléré)",
                    },

                    # ── Traitement audio
                    "normalize_audio": {
                        "type": "boolean",
                        "default": True,
                        "description": "Normaliser le volume de tout l'audio (LUFS)",
                    },
                    "target_loudness": {
                        "type": "number",
                        "minimum": -23,
                        "maximum": -1,
                        "default": -14,
                        "description": "Loudness cible en LUFS (-14 = YouTube, -23 = broadcast TV)",
                    },
                    "background_noise_reduction": {
                        "type": "boolean",
                        "default": True,
                        "description": "Réduire le bruit de fond",
                    },
                    "noise_reduction_level": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.3,
                        "description": "Intensité de la réduction de bruit (0 = désactivé, 1 = max)",
                    },
                    "fade_in_duration": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 5.0,
                        "default": 0.5,
                        "description": "Fondu d'entrée audio (secondes)",
                    },
                    "fade_out_duration": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 5.0,
                        "default": 0.5,
                        "description": "Fondu de sortie audio (secondes)",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },

            "qualite": {
                "type": "object",
                "title": "Boucle Qualité",
                "description": "Vérification automatique par IA (Gemini Vision) avant validation finale",
                "properties": {
                    # ── Iterations
                    "max_iterations": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 3,
                        "description": "Nombre max d'itérations de correction automatique",
                    },
                    "strictness": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium",
                        "description": "Niveau d'exigence (low = laisse passer les petits défauts)",
                    },

                    # ── Checks
                    "check_visual_quality": {
                        "type": "boolean",
                        "default": True,
                        "description": "Vérifier la qualité visuelle (exposition, netteté, artefacts)",
                    },
                    "check_audio_sync": {
                        "type": "boolean",
                        "default": True,
                        "description": "Vérifier la synchronisation audio/vidéo",
                    },
                    "check_subtitle_accuracy": {
                        "type": "boolean",
                        "default": True,
                        "description": "Vérifier la précision des sous-titres",
                    },
                    "check_branding_colors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Vérifier le respect de la charte couleur",
                    },
                    "check_every_frame": {
                        "type": "boolean",
                        "default": False,
                        "description": "Analyser chaque frame (lent mais très précis)",
                    },
                    "frame_sample_rate": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 300,
                        "default": 30,
                        "description": "Nombre de frames analysées par seconde (1 = une toutes les secondes)",
                    },

                    # ── Seuils
                    "min_confidence_score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.7,
                        "description": "Score de confiance minimum pour valider (0.7 = 70%)",
                    },
                    "min_duration_seconds": {
                        "type": "number",
                        "minimum": 5,
                        "maximum": 600,
                        "default": 30,
                        "description": "Durée minimale analysée (secondes) — ignorer les vidéos trop courtes",
                    },

                    # ── Corrections
                    "auto_correct_minor_issues": {
                        "type": "boolean",
                        "default": True,
                        "description": "Corriger automatiquement les petits défauts (recadrage, luminosité)",
                    },
                    "max_correction_attempts": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 3,
                        "description": "Tentatives max de correction avant escalade humaine",
                    },

                    # ── Rapport
                    "report_format": {
                        "type": "string",
                        "enum": ["detailed", "summary", "json-only"],
                        "default": "detailed",
                        "description": "Format du rapport de qualité",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },

            "validation": {
                "type": "object",
                "title": "Validation Humaine",
                "description": "Review finale par un humain avant export / publication",
                "properties": {
                    # ── Approbation
                    "require_approval": {
                        "type": "boolean",
                        "default": True,
                        "description": "Exiger une validation humaine avant export",
                    },
                    "auto_approve_if_no_response": {
                        "type": "boolean",
                        "default": False,
                        "description": "Approuver automatiquement après délai sans réponse",
                    },
                    "auto_approve_delay_hours": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 168,
                        "default": 24,
                        "description": "Délai avant approbation automatique (heures)",
                    },
                    "approval_timeout_hours": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 720,
                        "default": 48,
                        "description": "Délai max avant expiration de la demande (heures)",
                    },

                    # ── Workflow
                    "notify_on_complete": {
                        "type": "boolean",
                        "default": True,
                        "description": "Notifier quand la vidéo est prête pour review",
                    },
                    "notify_method": {
                        "type": "string",
                        "enum": ["telegram", "email", "both"],
                        "default": "telegram",
                        "description": "Méthode de notification",
                    },
                    "request_changes_msg": {
                        "type": "string",
                        "default": "",
                        "description": "Message personnalisé accompagnant la demande de review",
                    },

                    # ── Export
                    "export_on_approval": {
                        "type": "boolean",
                        "default": True,
                        "description": "Exporter automatiquement après validation",
                    },
                    "export_destination": {
                        "type": "string",
                        "enum": ["local", "s3", "youtube", "drive"],
                        "default": "local",
                        "description": "Destination après validation",
                    },
                    "keep_intermediate_files": {
                        "type": "boolean",
                        "default": False,
                        "description": "Conserver les fichiers intermédiaires (transcript, cut_list, etc.)",
                    },

                    # ── Communs
                    "mode": mode_field,
                    "api_key": api_key_field,
                },
            },
        }
        return schemas.get(agent_id, {"type": "object", "properties": {}})

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Vérifie le type d'une valeur."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        py_type = type_map.get(expected_type)
        if py_type is None:
            return True  # Type inconnu = pas de vérification
        return isinstance(value, py_type)


config_validator = ConfigValidator()
