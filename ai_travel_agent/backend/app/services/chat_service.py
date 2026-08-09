"""
Orchestrates a chat turn across a small set of specialized agents:

  itinerary, hotels, preference, general        -- conversational agents
  flight_booking, bus_booking, hotel_booking     -- booking-specialist agents
  clear_memory                                   -- deterministic action, no LLM

flight_booking and hotel_booking additionally run a real Amadeus search
BEFORE the LLM generates anything: slot_extraction_service pulls
origin/destination/dates out of the conversation, amadeus_service fetches
live offers, and the results are injected into the prompt as ground truth
-- the model is explicitly told not to invent numbers if no results came
back, rather than being trusted to "remember" figures accurately.
"""
import json
from collections.abc import Iterator

from app.config import settings
from app.services.amadeus_service import AmadeusError, amadeus_service
from app.services.intent_service import Intent, intent_service
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services.session_service import session_service
from app.services.slot_extraction_service import slot_extraction_service

# Per-agent system-prompt additions. Booking agents get a distinct persona
# from the general travel-planning ones, since their job is narrower.
AGENT_INSTRUCTIONS: dict[Intent, str] = {
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
    Intent.FLIGHT_BOOKING: (
        "You are a flight-booking specialist agent, not a general travel "
        "planner. Stay narrowly focused on flights -- do not re-plan the "
        "itinerary. If real search results were provided to you, present "
        "them clearly and ask the user to pick one. If none were provided, "
        "explain you couldn't find live results and ask for the missing "
        "detail (origin city, or a specific date) rather than inventing one."
    ),
    Intent.BUS_BOOKING: (
        "You are a bus/train-booking specialist agent, not a general travel "
        "planner. Stay narrowly focused on ground travel. There is no live "
        "booking system connected for this yet -- give general guidance on "
        "routes/operators and next steps, and say so plainly rather than "
        "inventing specific schedules or prices."
    ),
    Intent.HOTEL_BOOKING: (
        "You are a hotel-booking specialist agent, not a general travel "
        "planner. Stay narrowly focused on the stay itself. If real search "
        "results were provided to you, present them clearly and ask the "
        "user to pick one. If none were provided, say so and ask for the "
        "missing detail rather than inventing a hotel name or price."
    ),
    Intent.GENERAL: "",
}

CLEAR_MEMORY_REPLY = (
    "Done — I've cleared everything I remembered about you. We're starting fresh."
)

BOOKING_SUGGESTIONS = [
    {
        "agent": Intent.FLIGHT_BOOKING.value,
        "label": "✈Book a flight",
        "message": "Help me book a flight for this trip.",
    },
    {
        "agent": Intent.BUS_BOOKING.value,
        "label": "Book a bus/train",
        "message": "Help me book a bus or train for this trip.",
    },
    {
        "agent": Intent.HOTEL_BOOKING.value,
        "label": "Book a hotel",
        "message": "Help me book a hotel for this trip.",
    },
]


class ChatService:
    # ---------- non-streaming path (used by POST /api/chat) ----------
    def handle_message(
        self, user_id: str, message: str, agent: str | None = None
    ) -> tuple[str, list[str], str, list[dict]]:
        intent = intent_service.from_override(agent) or intent_service.classify(message)

        if intent is Intent.CLEAR_MEMORY:
            memory_service.delete_all(user_id=user_id)
            session_service.clear(user_id=user_id)
            return CLEAR_MEMORY_REPLY, [], intent.value, []

        relevant_memories = memory_service.search_relevant(query=message, user_id=user_id)
        booking_options, grounding = self.run_booking_search(user_id, message, intent)
        messages = self.build_messages(user_id, message, intent, relevant_memories, grounding)
        reply = llm_service.chat(messages=messages)

        self.persist_turn(user_id, message, reply)
        suggestions = BOOKING_SUGGESTIONS if intent is Intent.ITINERARY else []
        return reply, relevant_memories, intent.value, suggestions

    # ---------- streaming path (used by POST /api/chat/stream) ----------
    def handle_message_stream(
        self, user_id: str, message: str, agent: str | None = None
    ) -> Iterator[str]:
        """
        Yields newline-delimited JSON events:
          {"type": "intent", "data": "..."}              -- which agent handled this
          {"type": "memories", "data": [...]}              -- long-term memory recalled
          {"type": "booking_options", "data": {...}}       -- live Amadeus results, if any
          {"type": "token", "data": "..."}                 -- reply text, streamed
          {"type": "suggestions", "data": [...]}           -- follow-up agents (after itinerary)
          {"type": "done"}
          {"type": "error", "data": "..."}
        """
        intent = intent_service.from_override(agent) or intent_service.classify(message)
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

        booking_options, grounding = self.run_booking_search(user_id, message, intent)
        if booking_options:
            yield self.event("booking_options", {"kind": intent.value, "options": booking_options})

        messages = self.build_messages(user_id, message, intent, relevant_memories, grounding)

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

        if intent is Intent.ITINERARY:
            yield self.event("suggestions", BOOKING_SUGGESTIONS)

        yield self.event("done")

    # ---------- booking search (Amadeus) ----------
    def run_booking_search(
        self, user_id: str, message: str, intent: Intent
    ) -> tuple[list[dict], str]:
        """
        For flight_booking / hotel_booking only: extract slots, call
        Amadeus, and return (options, grounding_text). Returns ([], "")
        for every other intent, or if the search couldn't run for any
        reason -- the caller then just proceeds without live data.
        """
        if intent not in (Intent.FLIGHT_BOOKING, Intent.HOTEL_BOOKING):
            return [], ""

        slots = slot_extraction_service.extract(user_id, message)
        options: list[dict] = []

        try:
            destination_code = (
                amadeus_service.resolve_city_code(slots["destination"])
                if slots["destination"]
                else None
            )

            if intent is Intent.FLIGHT_BOOKING:
                origin_code = (
                    amadeus_service.resolve_city_code(slots["origin"])
                    if slots["origin"]
                    else None
                )
                if origin_code and destination_code:
                    options = amadeus_service.search_flights(
                        origin_code,
                        destination_code,
                        slots["departure_date"] or amadeus_service.default_future_date(),
                    )
            elif destination_code:
                check_in = slots["departure_date"] or amadeus_service.default_future_date()
                check_out = slots["return_date"] or amadeus_service.default_future_date(days=16)
                options = amadeus_service.search_hotels(destination_code, check_in, check_out)
        except AmadeusError:
            options = []  # fall through to the "no live results" grounding below

        if not options:
            grounding = (
                "No live search results are available right now (missing "
                "origin/destination, unresolved location, or no matches). "
                "Give general guidance only -- do NOT invent specific flight "
                "numbers, hotel names, or prices."
            )
            return [], grounding

        lines = [self.describe_option(o, intent) for o in options[:5]]
        grounding = (
            "Here are REAL search results, already fetched from Amadeus -- "
            "present them clearly and ask the user to pick one. Do not "
            "alter the numbers:\n" + "\n".join(lines)
        )
        return options, grounding

    @staticmethod
    def describe_option(o: dict, intent: Intent) -> str:
        if intent is Intent.FLIGHT_BOOKING:
            return (
                f"- {o['flight_number']} {o['departure_airport']}->{o['arrival_airport']}, "
                f"departs {o['departure_time']}, {o['stops']} stop(s), {o['price']} {o['currency']}"
            )
        return f"- {o['name']}: {o['price']} {o['currency']} ({o.get('room_description', '')[:60]})"

    # ---------- shared helpers ----------
    def build_messages(
        self,
        user_id: str,
        message: str,
        intent: Intent,
        memories: list[str],
        grounding: str = "",
    ) -> list[dict]:
        system_parts = [settings.system_prompt]

        instruction = AGENT_INSTRUCTIONS.get(intent, "")
        if instruction:
            system_parts.append(instruction)

        if grounding:
            system_parts.append(grounding)

        if memories:
            context_lines = "\n".join(f"- {m}" for m in memories)
            system_parts.append(f"Relevant past information about this user:\n{context_lines}")

        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        messages.extend(session_service.get_history(user_id))
        messages.append({"role": "user", "content": message})
        return messages

    @staticmethod
    def persist_turn(user_id: str, message: str, reply: str) -> None:
        session_service.add_turn(user_id, "user", message)
        session_service.add_turn(user_id, "assistant", reply)
        memory_service.add(message, user_id=user_id, role="user")
        memory_service.add(reply, user_id=user_id, role="assistant")

    @staticmethod
    def event(event_type: str, data=None) -> str:
        payload = {"type": event_type} if data is None else {"type": event_type, "data": data}
        return json.dumps(payload) + "\n"


chat_service = ChatService()