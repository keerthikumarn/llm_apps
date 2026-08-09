"""
Extracts structured travel-search parameters (origin, destination, dates)
from the conversation so the booking agents can call Amadeus without
making the user fill out a form.

Uses the local LLM in JSON-output mode. Any failure (bad JSON, model
error, missing fields) falls back to an all-None result -- callers then
skip the live search and fall back to general advisory text, rather than
crashing the turn over a parsing miss.
"""
import json

from app.services.llm_service import llm_service
from app.services.session_service import session_service

EXTRACTION_SYSTEM_PROMPT = """Extract travel search parameters from this conversation.
Respond with ONLY a JSON object, no other text, using this exact shape:
{"origin": "<city name or null>", "destination": "<city name or null>",
 "departure_date": "<YYYY-MM-DD or null>", "return_date": "<YYYY-MM-DD or null>"}

Rules:
- destination is required -- infer it from context (e.g. an itinerary discussed earlier in this conversation).
- If origin isn't mentioned, use null. Do not guess a random city.
- If a date isn't mentioned, use null.
- Output ONLY the JSON object. No explanation, no markdown fences."""

_EMPTY_RESULT = {"origin": None, "destination": None, "departure_date": None, "return_date": None}


class SlotExtractionService:
    def extract(self, user_id: str, latest_message: str) -> dict:
        history = session_service.get_history(user_id)
        convo_text = "\n".join(f'{m["role"]}: {m["content"]}' for m in history)
        convo_text += f"\nuser: {latest_message}"

        try:
            raw = llm_service.chat(
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": convo_text},
                ],
                json_mode=True,
            )
            parsed = json.loads(raw)
        except Exception:  # noqa: BLE001 - extraction miss just means no live search, not a crash
            return dict(_EMPTY_RESULT)

        return {
            "origin": parsed.get("origin") or None,
            "destination": parsed.get("destination") or None,
            "departure_date": parsed.get("departure_date") or None,
            "return_date": parsed.get("return_date") or None,
        }


slot_extraction_service = SlotExtractionService()