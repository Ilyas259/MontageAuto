"""
Templates de composition — Split Screen.
Speaker + B-roll côte à côte avec différents ratios.
"""

from agent3_montage.models import CompositionTemplate

SPLIT_50_50 = CompositionTemplate(
    name="split_50_50",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 0.5, "h": 1,
            "fit": "cover",
            "border_right": "1px solid rgba(255,255,255,0.15)",
        },
        "broll": {
            "x": 0.5, "y": 0, "w": 0.5, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.3},
        "exit": {"type": "fade_out", "duration": 0.2},
    },
    default_duration=6.0,
    subtitle_position="bottom",
)

SPLIT_70_30_SPEAKER = CompositionTemplate(
    name="split_70_30_speaker",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 0.7, "h": 1,
            "fit": "cover",
        },
        "broll": {
            "x": 0.7, "y": 0, "w": 0.3, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "slide_in_left", "duration": 0.4},
        "exit": {"type": "fade_out", "duration": 0.2},
    },
    default_duration=5.0,
    subtitle_position="bottom",
)

SPLIT_30_70_BROLL = CompositionTemplate(
    name="split_30_70_broll",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0.65, "w": 0.3, "h": 0.35,
            "fit": "cover",
            "border_radius": 8,
            "box_shadow": "0 4px 15px rgba(0,0,0,0.3)",
        },
        "broll": {
            "x": 0, "y": 0, "w": 1, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "zoom_in", "duration": 0.5},
        "exit": {"type": "fade_out", "duration": 0.2},
    },
    default_duration=7.0,
    subtitle_position="bottom",
)

SPLIT_TRIPLE = CompositionTemplate(
    name="split_triple",
    type="split",
    layout={
        "speaker": {
            "x": 0, "y": 0, "w": 0.333, "h": 1,
            "fit": "cover",
        },
        "broll_1": {
            "x": 0.333, "y": 0, "w": 0.333, "h": 1,
            "fit": "cover",
        },
        "broll_2": {
            "x": 0.666, "y": 0, "w": 0.334, "h": 1,
            "fit": "cover",
        },
    },
    animation={
        "entry": {"type": "fade_in", "duration": 0.3},
        "exit": {"type": "fade_out", "duration": 0.3},
    },
    default_duration=8.0,
    subtitle_position="bottom",
)
