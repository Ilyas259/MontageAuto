"""
Templates de composition — Full B-roll.
Visuel plein écran avec voix off superposée et sous-titres centrés.
"""

from agent3_montage.models import CompositionTemplate

FULL_BROLL_DEFAULT = CompositionTemplate(
    name="full_broll_default",
    type="full_broll",
    layout={
        "broll": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
        },
        "overlay": {
            "type": "gradient",
            "start_color": "rgba(0,0,0,0)",
            "end_color": "rgba(0,0,0,0.4)",
            "position": "bottom",
            "height": 0.3,
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.4},
        "exit": {"type": "fade_out", "duration": 0.3},
    },
    default_duration=6.0,
    subtitle_position="center",
)

FULL_BROLL_KEN_BURNS = CompositionTemplate(
    name="full_broll_ken_burns",
    type="full_broll",
    layout={
        "broll": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
            "ken_burns": {
                "type": "zoom_in",
                "start_scale": 1.0,
                "end_scale": 1.15,
                "start_x": 0, "start_y": 0,
                "end_x": 0.05, "end_y": 0.05,
            },
        },
        "overlay": {
            "type": "vignette",
            "intensity": 0.3,
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.5},
        "exit": {"type": "fade_out", "duration": 0.4},
    },
    default_duration=8.0,
    subtitle_position="bottom",
)

FULL_BROLL_STATIC = CompositionTemplate(
    name="full_broll_static",
    type="full_broll",
    layout={
        "broll": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "cut", "duration": 0},
        "exit": {"type": "cut", "duration": 0},
    },
    default_duration=4.0,
    subtitle_position="bottom",
)
