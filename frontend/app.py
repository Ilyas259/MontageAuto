"""Application Streamlit — Pipeline Montage Vidéo (Prototype).

Architecture schema-driven UI : le frontend est généré à partir des
JSON Schema exposés par l'API. Ajouter un nouvel agent = zéro code frontend.
"""

import streamlit as st

from frontend.config import APP_TITLE

# Configuration de la page
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar — navigation
st.sidebar.markdown(
    f"""
    <div style="text-align: center; padding: 16px 0;">
        <h1 style="font-size: 1.8em;">🎬</h1>
        <h3 style="margin: 0;">{APP_TITLE}</h3>
        <p style="color: gray; font-size: 0.8em;">Schema-driven UI</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.divider()

# Menu de navigation
page = st.sidebar.radio(
    "Navigation",
    options=["🎬 Pipeline", "⚙️ Configuration", "🔑 API Keys"],
    key="nav",
)

st.sidebar.divider()
st.sidebar.markdown(
    """
    **Pipeline** : 6 agents  
    🎙️ → ✂️ → 🎬 → 🎵 → ✅ → 👁️  

    *Frontend prototype — remplaçable par un frontend pro.*
    """
)

# Statut du backend (check rapide)
with st.sidebar:
    st.markdown("### 🔌 Connexion API")
    try:
        from frontend.services.api import api_client
        agents = api_client.list_agents()
        st.success(f"✅ {len(agents)} agents connectés")
    except Exception:
        st.warning("⚠️ Backend non accessible")
        st.caption("Lance `uvicorn backend.api.main:app --port 8001`")

# Routage des pages
if page == "⚙️ Configuration":
    from frontend.pages.agents import render as render_agents
    render_agents()
elif page == "🔑 API Keys":
    from frontend.pages.secrets import render as render_secrets
    render_secrets()
else:
    from frontend.pages.pipeline import render as render_pipeline
    render_pipeline()
