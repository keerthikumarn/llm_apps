"""
Orchestrates a single chat turn:
retrieve relevant memories -> build prompt -> call LLM -> persist turn.
"""
import json
from collections.abc import Iterator

from app.config import settings
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service


class ChatService:
    def handle_message(self, user_id: str, message: str) -> tuple[str, list[str]]:
        relevant_memories = memory_service.search_relevant(query=message, user_id=user_id)

        prompt = self._build_prompt(message, relevant_memories)
        reply = llm_service.chat(system_prompt=settings.system_prompt, user_message=prompt)

        memory_service.add(message, user_id=user_id, role="user")
        memory_service.add(reply, user_id=user_id, role="assistant")

        return reply, relevant_memories

    def handle_message_stream(self, user_id: str, message: str) -> Iterator[str]:
        """
        Same flow as handle_message, but yields newline-delimited JSON events
        as the reply is generated, instead of returning it all at once.
        """
        relevant_memories = memory_service.search_relevant(query=message, user_id=user_id)
        yield self._event("memories", relevant_memories)

        prompt = self._build_prompt(message, relevant_memories)

        chunks: list[str] = []
        try:
            for token in llm_service.stream_chat(
                system_prompt=settings.system_prompt, user_message=prompt
            ):
                chunks.append(token)
                yield self._event("token", token)
        except Exception as exc:  # noqa: BLE001
            yield self._event("error", str(exc))
            return

        reply = "".join(chunks)
        if reply:
            memory_service.add(message, user_id=user_id, role="user")
            memory_service.add(reply, user_id=user_id, role="assistant")

        yield self._event("done")

    @staticmethod
    def _event(event_type: str, data=None) -> str:
        payload = {"type": event_type} if data is None else {"type": event_type, "data": data}
        return json.dumps(payload) + "\n"

    @staticmethod
    def _build_prompt(message: str, memories: list[str]) -> str:
        if not memories:
            return message

        context_lines = "\n".join(f"- {m}" for m in memories)
        return (
            f"Relevant past information about this user:\n{context_lines}\n\n"
            f"Current message: {message}"
        )


chat_service = ChatService()