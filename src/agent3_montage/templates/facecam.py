"""
Templates de composition — Facecam.
Speaker seul face caméra, avec ou sans fond artistique.
"""

from agent3_montage.models import CompositionTemplate

FACECAM_DEFAULT = CompositionTemplate(
    name="facecam_default",
    type="facecam",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
            "border_radius": 0,
        },
        "overlay": {
            "type": "gradient",
            "start_color": "rgba(0,0,0,0)",
            "end_color": "rgba(0,0,0,0)",
            "position": "bottom",
            "height": 0.2,
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.3},
        "exit": {"type": "fade_out", "duration": 0.2},
    },
    default_duration=5.0,
    subtitle_position="bottom",
)

FACECAM_GREENSCREEN = CompositionTemplate(
    name="facecam_greenscreen",
    type="facecam",
    layout={
        "speaker": {
            "x": 0.3, "y": 0.05, "w": 0.4, "h": 0.9,
            "fit": "contain",
            "chroma_key": {
                "color": "#00FF00",
                "similarity": 0.4,
                "smoothness": 0.1,
                "spill": 0.1,
            },
        },
        "background": {
            "type": "solid",
            "color": "#1a1a2e",
        },
    },
    animation={
        "entry": {"type": "slide_in_left", "duration": 0.5},
        "exit": {"type": "fade_out", "duration": 0.3},
    },
    default_duration=8.0,
    subtitle_position="bottom",
)

FACECAM_SPEAKER_ONLY = CompositionTemplate(
    name="facecam_speaker_only",
    type="facecam",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.1},
        "exit": {"type": "fade_out", "duration": 0.1},
    },
    default_duration=3.0,
    subtitle_position="bottom",
)
