"""
Templates de composition — Transitions.
Définit les différents effets de transition entre segments.
"""

from agent3_montage.models import CompositionTemplate

TRANSITION_CUT = CompositionTemplate(
    name="transition_cut",
    type="transition",
    layout={},
    animation={},
    default_duration=0.0,
    subtitle_position="bottom",
)

TRANSITION_FADE = CompositionTemplate(
    name="transition_fade",
    type="transition",
    layout={},
    animation={
        "type": "crossfade",
        "duration": 0.3,
        "easing": "linear",
    },
    default_duration=0.3,
    subtitle_position="bottom",
)

TRANSITION_SLIDE = CompositionTemplate(
    name="transition_slide",
    type="transition",
    layout={
        "direction": "left",
    },
    animation={
        "type": "slide",
        "duration": 0.4,
        "easing": "cubic-bezier(0.25, 0.1, 0.25, 1.0)",
    },
    default_duration=0.4,
    subtitle_position="bottom",
)

TRANSITION_ZOOM = CompositionTemplate(
    name="transition_zoom",
    type="transition",
    layout={
        "zoom_direction": "in",
    },
    animation={
        "type": "zoom_blur",
        "duration": 0.5,
        "blur_max": 15,
    },
    default_duration=0.5,
    subtitle_position="bottom",
)

TRANSITION_SLIDE_UP = CompositionTemplate(
    name="transition_slide_up",
    type="transition",
    layout={
        "direction": "up",
    },
    animation={
        "type": "slide",
        "duration": 0.35,
        "easing": "cubic-bezier(0.4, 0.0, 0.2, 1.0)",
    },
    default_duration=0.35,
    subtitle_position="bottom",
)

TRANSITION_WIPE = CompositionTemplate(
    name="transition_wipe",
    type="transition",
    layout={
        "wipe_direction": "left",
    },
    animation={
        "type": "wipe",
        "duration": 0.4,
        "edge_width": 0.1,
    },
    default_duration=0.4,
    subtitle_position="bottom",
)
