"""Composant de rendu générique de formulaire JSON Schema.

Convertit un JSON Schema en formulaire Streamlit avec widgets adaptés.
Nouvel agent = nouveau schema = formulaire auto-généré (zéro code frontend).
Supporte text_area pour les longs textes, sliders adaptatifs, writeOnly.
"""

from typing import Any, Callable

import streamlit as st

from frontend.config import AGENT_LABELS, AGENT_DESCRIPTIONS

# Champs longs qui méritent un text_area
LONG_TEXT_FIELDS = {
    "system_prompt", "initial_prompt", "hotwords",
    "request_changes_msg", "subtitle_color",
}


def _smart_step(min_val: float, max_val: float) -> float:
    """Calcule un pas adapté à la plage de valeurs."""
    range_val = max_val - min_val
    if range_val <= 0.05:
        return 0.001
    if range_val <= 0.5:
        return 0.01
    if range_val <= 1.0:
        return 0.05
    if range_val <= 5.0:
        return 0.1
    if range_val <= 10.0:
        return 0.5
    return 1.0


def render_schema_form(
    agent_id: str,
    schema: dict[str, Any],
    current_values: dict[str, Any],
    key_prefix: str = "",
    on_change: Callable | None = None,
) -> dict[str, Any]:
    """Rendu d'un JSON Schema en formulaire Streamlit.

    Args:
        agent_id: Identifiant de l'agent.
        schema: JSON Schema avec "properties", "type", etc.
        current_values: Valeurs actuelles à pré-remplir.
        key_prefix: Préfixe pour les clés Streamlit (unicité).
        on_change: Callback optionnel lors d'un changement.

    Returns:
        Dictionnaire des valeurs saisies.
    """
    properties = schema.get("properties", {})
    result = {}

    # Titre de la section agent
    label = AGENT_LABELS.get(agent_id, agent_id)
    desc = schema.get("description") or AGENT_DESCRIPTIONS.get(agent_id, "")
    st.subheader(label)
    if desc:
        st.caption(desc)

    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        field_label = field_schema.get("title", field_name.replace("_", " ").title())
        field_desc = field_schema.get("description", "")
        default_value = field_schema.get("default")
        current_value = current_values.get(field_name, default_value)

        # Skip writeOnly fields (api_key) — géré ailleurs (page secrets)
        if field_schema.get("writeOnly"):
            continue

        key = f"{key_prefix}_{agent_id}_{field_name}"
        unique_key = f"form_{key}"

        # ── Si enum → selectbox ─────────────────────────────
        if "enum" in field_schema:
            options = field_schema["enum"]
            label_text = field_label
            if field_desc:
                label_text += f" ℹ️"
                st.caption(field_desc)
            result[field_name] = st.selectbox(
                label_text,
                options=options,
                index=options.index(current_value) if current_value in options else 0,
                key=unique_key,
                on_change=on_change,
            )

        # ── Boolean → checkbox ──────────────────────────────
        elif field_type == "boolean":
            label_text = field_label
            if field_desc:
                label_text += f" — {field_desc}"
            result[field_name] = st.checkbox(
                label_text,
                value=bool(current_value),
                key=unique_key,
                on_change=on_change,
            )

        # ── Number → slider adaptatif ───────────────────────
        elif field_type == "number":
            min_val = field_schema.get("minimum", 0.0)
            max_val = field_schema.get("maximum", 1.0)
            step = _smart_step(min_val, max_val)
            label_text = field_label
            if field_desc:
                label_text += f" ℹ️"
                st.caption(field_desc)
            result[field_name] = st.slider(
                label_text,
                min_value=float(min_val),
                max_value=float(max_val),
                value=float(current_value if current_value is not None else min_val),
                step=step,
                key=unique_key,
                on_change=on_change,
            )

        # ── Integer → number_input ──────────────────────────
        elif field_type == "integer":
            min_val = field_schema.get("minimum", 1)
            max_val = field_schema.get("maximum", 100)
            label_text = field_label
            if field_desc:
                label_text += f" ℹ️"
                st.caption(field_desc)
            result[field_name] = st.number_input(
                label_text,
                min_value=int(min_val),
                max_value=int(max_val),
                value=int(current_value if current_value is not None else min_val),
                step=1,
                key=unique_key,
                on_change=on_change,
            )

        # ── String long → text_area ─────────────────────────
        elif field_name in LONG_TEXT_FIELDS:
            label_text = field_label
            if field_desc:
                label_text += f" ℹ️"
                st.caption(field_desc)
            result[field_name] = st.text_area(
                label_text,
                value=str(current_value or ""),
                key=unique_key,
                on_change=on_change,
            )

        # ── String court → text_input ───────────────────────
        else:
            label_text = field_label
            if field_desc:
                label_text += f" ℹ️"
                st.caption(field_desc)
            result[field_name] = st.text_input(
                label_text,
                value=str(current_value or ""),
                key=unique_key,
                on_change=on_change,
            )

    st.divider()
    return result


def render_config_summary(agent_id: str, config: dict[str, Any]):
    """Affiche un résumé compact de la configuration d'un agent."""
    label = AGENT_LABELS.get(agent_id, agent_id)
    with st.expander(label, expanded=False):
        st.json(config)
