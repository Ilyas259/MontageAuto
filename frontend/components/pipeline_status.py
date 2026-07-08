"""Composant d'affichage du statut d'un pipeline en cours."""

from typing import Any

import streamlit as st

from frontend.config import STATE_COLORS


def display_pipeline_status(pipeline: dict[str, Any]):
    """Affiche le statut visuel d'un pipeline."""
    state = pipeline.get("state", "unknown")
    pipeline_id = pipeline.get("id", "?")
    created_at = pipeline.get("created_at", "")

    color = STATE_COLORS.get(state, "gray")
    status_emoji = {
        "idle": "⏸️",
        "running": "▶️",
        "cancelling": "⏹️",
        "cancelled": "⏹️",
        "completed": "✅",
        "failed": "❌",
    }.get(state, "❓")

    st.markdown(
        f"""
        <div style="
            border: 2px solid {color};
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            background-color: rgba(128,128,128,0.05);
        ">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-size: 1.2em; font-weight: bold;">
                    {status_emoji} Pipeline <code>{pipeline_id[:8]}…</code>
                </span>
                <span style="
                    background: {color};
                    color: white;
                    padding: 2px 10px;
                    border-radius: 12px;
                    font-size: 0.85em;
                ">{state}</span>
            </div>
            <div style="margin-top: 8px; font-size: 0.85em; color: gray;">
                Créé le {created_at[:19] if created_at else "?"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Barre de progression (si running)
    if state == "running":
        st.progress(0.5, text="Pipeline en cours d'exécution…")
    elif state == "completed":
        st.progress(1.0, text="Pipeline terminé")
    elif state == "failed":
        st.progress(1.0, text="Pipeline échoué")


def display_agent_progress(agents_results: list[dict]):
    """Affiche l'avancement de chaque agent."""
    if not agents_results:
        return

    st.markdown("### Avancement par agent")
    for agent in agents_results:
        agent_id = agent.get("agent_id", "?")
        status = agent.get("status", "pending")
        error = agent.get("error")

        emoji = {
            "completed": "✅",
            "running": "⏳",
            "failed": "❌",
            "cancelled": "⏹️",
            "pending": "⏸️",
        }.get(status, "❓")

        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"**{emoji}**")
        with col2:
            if error:
                st.markdown(f"**{agent_id}** — {status} ⚠️ `{error}`")
            else:
                st.markdown(f"**{agent_id}** — {status}")
