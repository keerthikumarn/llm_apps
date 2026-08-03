"""
Short-term, in-process conversation history.

This is deliberately separate from mem0: mem0 stores distilled, durable
facts across sessions; this stores the raw last few turns of the *current*
conversation so the model can resolve things like "make it 3 days instead"
without waiting on mem0's extraction/retrieval cycle.

Not persisted — resets when the server restarts. Keyed by user_id, capped
to the last N messages to bound prompt size.
"""
from collections import defaultdict, deque
from app.config import settings


class SessionService:
    def __init__(self) -> None:
        self.history: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=settings.session_history_max_messages)
        )

    def get_history(self, user_id: str) -> list[dict]:
        """Return the recent raw turns for this user, oldest first."""
        return list(self.history[user_id])

    def add_turn(self, user_id: str, role: str, content: str) -> None:
        self.history[user_id].append({"role": role, "content": content})

    def clear(self, user_id: str) -> None:
        self.history.pop(user_id, None)


session_service = SessionService()