"""State Machine du pipeline.

Gère les transitions d'état avec validation. Émet des événements SSE à chaque transition.

États : idle → running → agent_N_in_progress → ... → completed / failed / cancelled
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


# Définition des états
STATES = [
    "idle",
    "running",
    "agent_1_in_progress",
    "agent_2_in_progress",
    "agent_3_in_progress",
    "agent_4_in_progress",
    "agent_5_in_progress",
    "agent_6_in_progress",
    "completed",
    "failed",
    "cancelling",
    "cancelled",
    "paused",
]

TERMINAL_STATES = {"completed", "failed", "cancelled"}

# Transitions valides : (from_state, to_state)
VALID_TRANSITIONS: set[tuple[str, str]] = {
    ("idle", "running"),
    ("running", "agent_1_in_progress"),
    ("agent_1_in_progress", "agent_2_in_progress"),
    ("agent_2_in_progress", "agent_3_in_progress"),
    ("agent_3_in_progress", "agent_4_in_progress"),
    ("agent_4_in_progress", "agent_5_in_progress"),
    ("agent_5_in_progress", "agent_6_in_progress"),
    ("agent_6_in_progress", "completed"),
    # Erreur possible depuis n'importe quel état actif
    ("agent_1_in_progress", "failed"),
    ("agent_2_in_progress", "failed"),
    ("agent_3_in_progress", "failed"),
    ("agent_4_in_progress", "failed"),
    ("agent_5_in_progress", "failed"),
    ("agent_6_in_progress", "failed"),
    # Cancel depuis n'importe quel état actif
    ("agent_1_in_progress", "cancelling"),
    ("agent_2_in_progress", "cancelling"),
    ("agent_3_in_progress", "cancelling"),
    ("agent_4_in_progress", "cancelling"),
    ("agent_5_in_progress", "cancelling"),
    ("agent_6_in_progress", "cancelling"),
    ("cancelling", "cancelled"),
    # Pause/Resume
    ("agent_1_in_progress", "paused"),
    ("agent_2_in_progress", "paused"),
    ("agent_3_in_progress", "paused"),
    ("agent_4_in_progress", "paused"),
    ("agent_5_in_progress", "paused"),
    ("agent_6_in_progress", "paused"),
    ("paused", "agent_1_in_progress"),
    ("paused", "agent_2_in_progress"),
    ("paused", "agent_3_in_progress"),
    ("paused", "agent_4_in_progress"),
    ("paused", "agent_5_in_progress"),
    ("paused", "agent_6_in_progress"),
}


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""


class PipelineStateMachine:
    """Machine à états pour un pipeline individuel."""

    def __init__(self, pipeline_id: str, on_transition: Callable | None = None):
        self.pipeline_id = pipeline_id
        self._state: str = "idle"
        self._transitions: list[StateTransition] = []
        self._on_transition = on_transition
        self._cancel_requested = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    @property
    def is_running(self) -> bool:
        return self._state not in TERMINAL_STATES and self._state != "idle"

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def can_transition_to(self, new_state: str) -> bool:
        """Vérifie si une transition est valide."""
        if new_state not in STATES:
            return False
        if self._state in TERMINAL_STATES:
            return False
        return (self._state, new_state) in VALID_TRANSITIONS

    def transition(self, new_state: str, reason: str = "") -> bool:
        """Tente une transition. Retourne True si réussie."""
        if not self.can_transition_to(new_state):
            return False

        if new_state == "cancelling":
            self._cancel_requested = True

        old_state = self._state
        self._state = new_state
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        self._transitions.append(transition)

        if self._on_transition:
            self._on_transition(
                self.pipeline_id,
                old_state=old_state,
                new_state=new_state,
                reason=reason,
            )

        return True

    def get_current_agent_order(self) -> int | None:
        """Retourne le numéro de l'agent en cours, ou None."""
        for i in range(1, 7):
            if self._state == f"agent_{i}_in_progress":
                return i
        return None

    def history(self) -> list[dict]:
        """Retourne l'historique des transitions."""
        return [
            {
                "from": t.from_state,
                "to": t.to_state,
                "timestamp": t.timestamp,
                "reason": t.reason,
            }
            for t in self._transitions
        ]
