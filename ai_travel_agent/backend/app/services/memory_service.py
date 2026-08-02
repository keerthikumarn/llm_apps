"""
Wraps mem0's Memory client.

All mem0-specific API quirks (e.g. search()/get_all() wanting
filters={"user_id": ...} while add() wants user_id=... directly)
are isolated here so the rest of the app never touches mem0 directly.
"""
from mem0 import Memory

from app.config import settings


def _build_config() -> dict:
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": settings.qdrant_host,
                "port": settings.qdrant_port,
                "collection_name": settings.qdrant_collection,
                "embedding_model_dims": settings.embed_dims,
            },
        },
        "llm": {
            "provider": "ollama",
            "config": {
                "model": settings.chat_model,
                "temperature": 0,
                "max_tokens": 2000,
                "ollama_base_url": settings.ollama_base_url,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": settings.embed_model,
                "ollama_base_url": settings.ollama_base_url,
            },
        },
    }


class MemoryService:
    """Thin, testable wrapper around mem0's Memory client."""

    def __init__(self) -> None:
        self.memory = Memory.from_config(_build_config())

    def search_relevant(self, query: str, user_id: str, limit: int | None = None) -> list[str]:
        """Return a list of memory strings relevant to the query."""
        limit = limit or settings.memory_search_limit
        result = self.memory.search(query=query, filters={"user_id": user_id}, limit=limit)
        return [item["memory"] for item in result.get("results", []) if "memory" in item]

    def get_all(self, user_id: str) -> list[dict]:
        """Return all stored memories for a user."""
        result = self.memory.get_all(filters={"user_id": user_id})
        return result.get("results", [])

    def add(self, text: str, user_id: str, role: str) -> None:
        """Store a piece of conversation text against a user."""
        self.memory.add(text, user_id=user_id, metadata={"role": role})

    def delete_all(self, user_id: str) -> None:
        """Delete all memories for a user."""
        self.memory.delete_all(user_id=user_id)


# Single shared instance — mem0's Memory client is expensive to construct
# (it opens connections to Qdrant/Ollama), so we build it once at import time.
memory_service = MemoryService()