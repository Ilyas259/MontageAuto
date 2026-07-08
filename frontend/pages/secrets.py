"""Page de gestion des clés API."""

import streamlit as st

from frontend.services.api import api_client


def render():
    st.title("🔑 Clés API")
    st.markdown(
        "Renseigne ici les clés API des services externes. "
        "Elles sont stockées dans `~/.video-automation/secrets.yaml` "
        "— hors du dépôt git et jamais partagées."
    )
    st.caption("Ces clés ne sont utilisées que quand un agent est en mode **api**.")

    try:
        resp = api_client.get_secrets()
        services = resp.get("services", [])
        configured_count = resp.get("configured_count", 0)
    except Exception as e:
        st.error(f"Impossible de contacter l'API : {e}")
        return

    st.markdown(f"### Statut ({configured_count}/{len(services)} configurées)")

    for svc in services:
        service_id = svc["service"]
        label = svc["label"]
        configured = svc["configured"]

        with st.container(border=True):
            cols = st.columns([3, 4, 2, 1])
            with cols[0]:
                st.markdown(f"**{label}**")
                st.caption(service_id)
            with cols[1]:
                if configured:
                    st.success("✅ Configurée")
                else:
                    st.warning("❌ Non configurée")

            with cols[2]:
                existing_key = api_client.get_secret(service_id).get("configured", False)
                new_key = st.text_input(
                    "Clé API",
                    type="password",
                    placeholder="sk-..." if not configured else "••••••••",
                    key=f"key_input_{service_id}",
                    label_visibility="collapsed",
                )

            with cols[3]:
                if new_key:
                    if st.button("💾", key=f"save_{service_id}"):
                        api_client.set_secret(service_id, new_key)
                        st.success(f"{label} enregistrée !")
                        st.rerun()
                if configured:
                    if st.button("🗑️", key=f"del_{service_id}"):
                        api_client.delete_secret(service_id)
                        st.success(f"{label} supprimée")
                        st.rerun()
