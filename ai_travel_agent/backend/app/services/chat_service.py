"""
Orchestrates a chat turn:
classify intent -> (short-circuit for clear_memory) -> retrieve long-term
memory -> assemble messages (system + short-term history + current) ->
call LLM -> persist to both short-term session history and long-term memory.
"""
import json
from collections.abc import Iterator

from app.config import settings
from app.services.intent_service import Intent, intent_service
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services.session_service import session_service

# Per-intent additions to the base system prompt. Empty string = no addition.
INTENT_INSTRUCTIONS: dict[Intent, str] = {
    Intent.ITINERARY: (
        "The user wants a day-by-day itinerary. Structure your reply with "
        "clear day headers (Day 1, Day 2, ...) and concrete activities/timing."
    ),
    Intent.HOTELS: (
        "The user wants hotel or accommodation recommendations. Give a short "
        "list with a one-line reason for each, matched to any known budget "
        "or style preferences."
    ),
    Intent.PREFERENCE: (
        "The user is sharing a personal travel preference. Acknowledge it "
        "briefly and naturally."
    ),
    Intent.GENERAL: "",
}

CLEAR_MEMORY_REPLY = (
    "Done — I've cleared everything I remembered about you. We're starting fresh."
)


class ChatService:
    # ---------- non-streaming path (used by POST /api/chat) ----------
    def handle_message(self, user_id: str, message: str) -> tuple[str, list[str], str]:
        intent = intent_service.classify(message)

        if intent is Intent.CLEAR_MEMORY:
            memory_service.delete_all(user_id=user_id)
            session_service.clear(user_id=user_id)
            return CLEAR_MEMORY_REPLY, [], intent.value

        relevant_memories = memory_service.search_relevant(query=message, user_id=user_id)
        messages = self.build_messages(user_id, message, intent, relevant_memories)
        reply = llm_service.chat(messages=messages)

        self.persist_turn(user_id, message, reply)
        return reply, relevant_memories, intent.value

    # ---------- streaming path (used by POST /api/chat/stream) ----------
    def handle_message_stream(self, user_id: str, message: str) -> Iterator[str]:
        """
        Yields newline-delimited JSON events:
          {"type": "intent", "data": "..."}      -- sent first, always
          {"type": "memories", "data": [...]}    -- sent once (empty for clear_memory)
          {"type": "token", "data": "..."}        -- sent repeatedly
          {"type": "done"}                        -- sent once, at the end
          {"type": "error", "data": "..."}        -- sent if generation fails
        """
        intent = intent_service.classify(message)
        yield self.event("intent", intent.value)

        if intent is Intent.CLEAR_MEMORY:
            memory_service.delete_all(user_id=user_id)
            session_service.clear(user_id=user_id)
            yield self.event("memories", [])
            yield self.event("token", CLEAR_MEMORY_REPLY)
            yield self.event("done")
            return

        relevant_memories = memory_service.search_relevant(query=message, user_id=user_id)
        yield self.event("memories", relevant_memories)

        messages = self.build_messages(user_id, message, intent, relevant_memories)

        chunks: list[str] = []
        try:
            for token in llm_service.stream_chat(messages=messages):
                chunks.append(token)
                yield self.event("token", token)
        except Exception as exc:  # noqa: BLE001
            yield self.event("error", str(exc))
            return

        reply = "".join(chunks)
        if reply:
            self.persist_turn(user_id, message, reply)

        yield self.event("done")

    # ---------- shared helpers ----------
    def build_messages(
        self, user_id: str, message: str, intent: Intent, memories: list[str]
    ) -> list[dict]:
        system_parts = [settings.system_prompt]

        instruction = INTENT_INSTRUCTIONS.get(intent, "")
        if instruction:
            system_parts.append(instruction)

        if memories:
            context_lines = "\n".join(f"- {m}" for m in memories)
            system_parts.append(f"Relevant past information about this user:\n{context_lines}")

        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        messages.extend(session_service.get_history(user_id))  # short-term context
        messages.append({"role": "user", "content": message})
        return messages

    @staticmethod
    def persist_turn(user_id: str, message: str, reply: str) -> None:
        # Short-term: raw turns, for immediate follow-up resolution.
        session_service.add_turn(user_id, "user", message)
        session_service.add_turn(user_id, "assistant", reply)
        # Long-term: mem0 extracts durable facts from these.
        memory_service.add(message, user_id=user_id, role="user")
        memory_service.add(reply, user_id=user_id, role="assistant")

    @staticmethod
    def event(event_type: str, data=None) -> str:
        payload = {"type": event_type} if data is None else {"type": event_type, "data": data}
        return json.dumps(payload) + "\n"


chat_service = ChatService()