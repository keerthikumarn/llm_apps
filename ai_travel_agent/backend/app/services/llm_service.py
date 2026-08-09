"""Wraps calls to the local Ollama chat model."""
from collections.abc import Iterator
from ollama import Client
from app.config import settings

class LLMService:
    def __init__(self) -> None:
        self._client = Client(host=settings.ollama_base_url)

    def chat(self, messages: list[dict], json_mode: bool = False) -> str:
        """Send a chat request with a full message list, return the reply text.

        json_mode=True asks Ollama to constrain output to valid JSON --
        used for structured extraction calls, not free-form replies.
        """
        kwargs: dict = {"model": settings.chat_model, "messages": messages}
        if json_mode:
            kwargs["format"] = "json"
        response = self._client.chat(**kwargs)
        content = response["message"]["content"]
        if not content:
            raise ValueError("Received empty response from the local model.")
        return content

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        """Send a chat request with a full message list, yield reply text incrementally."""
        stream = self._client.chat(model=settings.chat_model, messages=messages, stream=True)
        for chunk in stream:
            token = chunk["message"]["content"]
            if token:
                yield token


llm_service = LLMService()