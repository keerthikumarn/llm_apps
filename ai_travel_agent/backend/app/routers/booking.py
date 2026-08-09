"""
Dummy booking confirmation.

No real payment or reservation happens here -- this simulates the final
"pay and confirm" step after a real Amadeus search, generating a fake
confirmation code so the flow feels complete end-to-end. Swapping in a
real payment provider later only means replacing the body of this one
function; nothing else in the app needs to change.
"""
import random
import string

from fastapi import APIRouter

from app.schemas import BookingConfirmRequest, BookingConfirmResponse
from app.services.memory_service import memory_service

router = APIRouter(prefix="/api/booking", tags=["booking"])


@router.post("/confirm", response_model=BookingConfirmResponse)
def confirm_booking(payload: BookingConfirmRequest) -> BookingConfirmResponse:
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    label = payload.option.get("flight_number") or payload.option.get("name") or "your booking"
    price = payload.option.get("price", "")
    currency = payload.option.get("currency", "")

    # Record the booking as a durable memory, so future turns (and the
    # memory sidebar) reflect it -- e.g. "User booked 6E123 to DEL."
    summary = f"User booked {label} ({payload.kind}) for {price} {currency}. Confirmation: {code}."
    memory_service.add(summary, user_id=payload.user_id, role="assistant")

    return BookingConfirmResponse(
        confirmation_code=code,
        message=(
            f"Payment successful — {label} is confirmed. "
            f"Reference: {code}. (No real charge was made; this is a demo booking.)"
        ),
    )