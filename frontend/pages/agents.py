"""Page de configuration des agents."""

import streamlit as st

from frontend.config import AGENT_LABELS, AGENT_ORDER, MODES, MODE_LABELS, MODE_DESCRIPTIONS, PROFILES
from frontend.services.api import api_client
from frontend.components.schema_form import render_schema_form


def render():
    st.title("⚙️ Configuration du pipeline")

    # === Bascule globale du mode ===
    st.markdown("### 🌐 Mode d'exécution")
    st.caption("Choisis le mode global — chaque agent peut le surcharger dans son onglet.")

    global_mode = st.selectbox(
        "Mode global",
        options=MODES,
        format_func=lambda m: MODE_LABELS.get(m, m),
        index=0,
        key="global_mode_selector",
    )
    selected_mode_desc = MODE_DESCRIPTIONS.get(global_mode, "")
    if selected_mode_desc:
        st.info(selected_mode_desc, icon="ℹ️")

    # Sélection du profil
    st.markdown("### Profil de qualité")
    st.caption(
        "Le profil détermine les réglages par défaut de tous les agents. "
        "Tu peux ensuite ajuster chaque agent individuellement."
    )

    current_profile = st.selectbox(
        "Profil actif",
        options=PROFILES,
        index=0,
        key="profile_selector",
    )

    # Afficher les agents par ordre
    st.markdown("### Paramètres par agent")
    st.caption(
        "Chaque agent a sa propre configuration. "
        "Les valeurs par défaut viennent du profil sélectionné. "
        "Tes modifications sont sauvegardées localement."
    )

    # Dictionnaire pour stocker toutes les configs modifiées
    session_key = "agent_configs"
    if session_key not in st.session_state:
        st.session_state[session_key] = {}

    tabs = st.tabs([AGENT_LABELS.get(a, a) for a in AGENT_ORDER])

    for idx, agent_id in enumerate(AGENT_ORDER):
        with tabs[idx]:
            try:
                # Récupérer le schéma et la config actuelle
                schema = api_client.get_agent_schema(agent_id)
                current_config = api_client.get_agent_config(agent_id)

                # Rendu du formulaire
                values = render_schema_form(
                    agent_id=agent_id,
                    schema=schema,
                    current_values=current_config,
                    key_prefix="config",
                )

                # Bouton sauvegarde
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button(f"💾 Sauvegarder", key=f"save_{agent_id}"):
                        api_client.save_agent_config(agent_id, values)
                        st.success(f"Configuration {agent_id} sauvegardée")

                with col2:
                    if st.button(f"🔄 Réinitialiser", key=f"reset_{agent_id}"):
                        # Efface la config utilisateur
                        api_client.save_agent_config(agent_id, {})
                        st.rerun()

            except Exception as e:
                st.error(f"Erreur API pour {agent_id}: {e}")
                st.info("Assure-toi que le backend FastAPI est lancé.")
