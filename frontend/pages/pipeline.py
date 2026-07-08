"""Page d'exécution du pipeline."""

import json
import time
from typing import Any

import streamlit as st

from frontend.config import AGENT_LABELS, AGENT_ORDER
from frontend.services.api import api_client
from frontend.components.pipeline_status import display_pipeline_status, display_agent_progress


def render():
    st.title("🎬 Lancement du pipeline")

    # Section upload
    st.markdown("### Vidéo source")
    uploaded_file = st.file_uploader(
        "Choisis une vidéo MP4 à traiter",
        type=["mp4", "mov", "avi"],
        key="video_uploader",
    )

    if uploaded_file:
        st.video(uploaded_file)
        st.session_state["video_uploaded"] = True
        st.session_state["video_name"] = uploaded_file.name

    # Section paramètres du run
    st.markdown("### Paramètres d'exécution")
    col1, col2 = st.columns(2)
    with col1:
        output_name = st.text_input(
            "Nom de sortie",
            value="ma_video_finale",
            help="Nom du fichier vidéo final (sans extension)",
        )
    with col2:
        keep_preview = st.checkbox(
            "Conserver les fichiers intermédiaires",
            value=True,
            help="Utile pour déboguer ou re-mixer",
        )

    # Override rapide par agent (activer/désactiver)
    st.markdown("### Activer/Désactiver des agents")
    st.caption("Décoche un agent pour le skipper dans le pipeline")

    agent_enabled = {}
    cols = st.columns(3)
    for idx, agent_id in enumerate(AGENT_ORDER):
        with cols[idx % 3]:
            agent_enabled[agent_id] = st.checkbox(
                AGENT_LABELS.get(agent_id, agent_id),
                value=True,
                key=f"enable_{agent_id}",
            )

    # Bouton de lancement
    st.divider()
    col_run, col_status = st.columns([1, 3])
    with col_run:
        can_run = st.session_state.get("video_uploaded", False)
        run_button = st.button(
            "🚀 Lancer le pipeline",
            type="primary",
            disabled=not can_run,
            use_container_width=True,
        )

    if not can_run:
        with col_status:
            st.info("📤 Upload une vidéo pour activer le lancement")

    # Exécution
    if run_button:
        _run_pipeline(output_name, keep_preview, agent_enabled)

    # Section historique des pipelines
    st.divider()
    _render_history()


def _run_pipeline(output_name: str, keep_preview: bool, agent_enabled: dict):
    """Crée et lance un pipeline."""
    with st.spinner("Création du pipeline…"):
        try:
            # 1. Créer le pipeline
            pipeline_config = {
                "profile": "natural",
                "output_name": output_name,
                "keep_preview": keep_preview,
            }
            result = api_client.create_pipeline(pipeline_config)
            pipeline_id = result.get("pipeline_id", "?")

            # 2. Configurer les agents activés/désactivés
            run_params = {
                agent_id: {"enabled": enabled}
                for agent_id, enabled in agent_enabled.items()
            }

            # 3. Démarrer
            api_client.start_pipeline(pipeline_id, {"run_params": run_params})

            st.success(f"Pipeline {pipeline_id} démarré !")

            # 4. Polling du statut (simulation)
            status_placeholder = st.empty()
            progress_bar = st.progress(0, text="Exécution…")

            for step in range(1, 8):
                time.sleep(1.5)
                progress = min(step / 7, 1.0)
                progress_bar.progress(progress, text=f"Agent {step}/7…")

                try:
                    pipeline = api_client.get_pipeline(pipeline_id)
                    with status_placeholder.container():
                        display_pipeline_status(pipeline)

                    state = pipeline.get("state", "")
                    if state in ("completed", "failed", "cancelled"):
                        break
                except Exception:
                    pass

            progress_bar.progress(1.0, text="Terminé")

            # 5. Résultat final
            try:
                result_data = api_client.get_pipeline_result(pipeline_id)
                st.json(result_data)
            except Exception:
                st.info("Résultat final en attente du backend complet")

        except Exception as e:
            st.error(f"Erreur de lancement : {e}")
            st.info("Vérifie que le backend FastAPI tourne sur le port 8001")


def _render_history():
    """Affiche l'historique des pipelines récents."""
    st.markdown("### 📋 Historique des pipelines")

    try:
        pipelines = api_client.list_pipelines(limit=10)
        if not pipelines:
            st.info("Aucun pipeline lancé pour l'instant")
            return

        for p in pipelines:
            display_pipeline_status(p)
            if p.get("result"):
                with st.expander("Voir le résultat"):
                    st.json(p["result"])

    except Exception as e:
        st.warning(f"Impossible de charger l'historique : {e}")
