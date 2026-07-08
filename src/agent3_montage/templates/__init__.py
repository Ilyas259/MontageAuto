"""
Registre central des templates de composition.
Chaque template est importé et enregistré automatiquement via register_all().
"""

from agent3_montage.models import CompositionTemplate
from agent3_montage.template_engine import TemplateEngine
from agent3_montage.templates.facecam import (
    FACECAM_DEFAULT,
    FACECAM_GREENSCREEN,
    FACECAM_SPEAKER_ONLY,
)
from agent3_montage.templates.split import (
    SPLIT_50_50,
    SPLIT_70_30_SPEAKER,
    SPLIT_30_70_BROLL,
    SPLIT_TRIPLE,
)
from agent3_montage.templates.full_broll import (
    FULL_BROLL_DEFAULT,
    FULL_BROLL_KEN_BURNS,
    FULL_BROLL_STATIC,
)
from agent3_montage.templates.transitions import (
    TRANSITION_CUT,
    TRANSITION_FADE,
    TRANSITION_SLIDE,
    TRANSITION_ZOOM,
)


def register_all() -> None:
    """Enregistre tous les templates dans le registre global."""
    templates = [
        FACECAM_DEFAULT,
        FACECAM_GREENSCREEN,
        FACECAM_SPEAKER_ONLY,
        SPLIT_50_50,
        SPLIT_70_30_SPEAKER,
        SPLIT_30_70_BROLL,
        SPLIT_TRIPLE,
        FULL_BROLL_DEFAULT,
        FULL_BROLL_KEN_BURNS,
        FULL_BROLL_STATIC,
        TRANSITION_CUT,
        TRANSITION_FADE,
        TRANSITION_SLIDE,
        TRANSITION_ZOOM,
    ]
    for t in templates:
        TemplateEngine.register(t)
