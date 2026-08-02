"""Wraps calls to the local Ollama chat model."""
from collections.abc import Iterator
from ollama import Client
from app.config import settings


class LLMService:
    def __init__(self) -> None:
        self._client = Client(host=settings.ollama_base_url)

    def chat(self, system_prompt: str, user_message: str) -> str:
        """Send a single-turn chat request and return the full reply text."""
        response = self._client.chat(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        content = response["message"]["content"]
        if not content:
            raise ValueError("Received empty response from the local model.")
        return content

    def stream_chat(self, system_prompt: str, user_message: str) -> Iterator[str]:
        """Send a single-turn chat request and yield reply text incrementally."""
        stream = self._client.chat(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )
        for chunk in stream:
            token = chunk["message"]["content"]
            if token:
                yield token


llm_service = LLMService()