"""
Classifies each incoming message into a coarse intent so chat_service can
route it — different system-prompt instructions per intent, or in the
clear_memory case, bypass generation entirely for a deterministic action.

Classification uses the same local LLM with a strict, single-word-output
prompt. If the model returns anything unexpected, we fail safe to GENERAL
rather than erroring the whole turn out.
"""
from enum import StrEnum

from app.services.llm_service import llm_service


class Intent(StrEnum):
    ITINERARY = "itinerary"
    HOTELS = "hotels"
    PREFERENCE = "preference"
    CLEAR_MEMORY = "clear_memory"
    FLIGHT_BOOKING = "flight_booking"
    BUS_BOOKING = "bus_booking"
    HOTEL_BOOKING = "hotel_booking"
    GENERAL = "general"


CLASSIFY_SYSTEM_PROMPT = """You classify a traveler's chat message into exactly one category.
Respond with ONLY the category word — no punctuation, no explanation, nothing else.

Categories:
itinerary - asking for a day-by-day travel plan or schedule
hotels - asking for hotel or accommodation recommendations (not booking, just suggestions)
preference - stating a personal travel preference or fact about themselves
clear_memory - asking to forget, reset, or clear what's remembered about them
flight_booking - asking for help booking or finding a flight
bus_booking - asking for help booking or finding a bus/train
hotel_booking - asking for help booking a specific hotel/stay
general - anything else (greetings, general questions, follow-ups, small talk)"""

VALID_VALUES = {i.value for i in Intent}


class IntentService:
    def classify(self, message: str) -> Intent:
        try:
            raw = llm_service.chat(
                messages=[
                    {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ]
            )
        except Exception:  # noqa: BLE001 - classification failure should never break the chat
            return Intent.GENERAL

        first_word = raw.strip().lower().split()[0] if raw.strip() else ""
        cleaned = first_word.strip(".,!?\"'")

        return Intent(cleaned) if cleaned in VALID_VALUES else Intent.GENERAL

    @staticmethod
    def from_override(agent: str | None) -> Intent | None:
        """
        Validate a direct agent selection from the frontend (e.g. a clicked
        suggestion button). Returns None if the value isn't a recognized
        agent, so the caller can fall back to normal classification.
        """
        if not agent:
            return None
        cleaned = agent.strip().lower()
        return Intent(cleaned) if cleaned in VALID_VALUES else None


intent_service = IntentService()