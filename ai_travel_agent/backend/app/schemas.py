"""Pydantic models defining the API's request/response contracts."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user")
    message: str = Field(..., min_length=1, description="The user's chat message")
    agent: str | None = Field(
        default=None,
        description=(
            "Optional direct agent selection (e.g. 'flight_booking'), bypassing "
            "intent classification. Set when the user taps a suggestion button "
            "rather than typing free text."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    memories_used: list[str] = Field(default_factory=list)
    intent: str = "general"
    suggestions: list[dict] = Field(default_factory=list)


class MemoryItem(BaseModel):
    id: str | None = None
    memory: str
    metadata: dict | None = None


class MemoryListResponse(BaseModel):
    user_id: str
    memories: list[MemoryItem]


class DeleteMemoryResponse(BaseModel):
    user_id: str
    deleted: bool


class BookingConfirmRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    kind: str = Field(..., description="'flight_booking' or 'hotel_booking'")
    option: dict = Field(..., description="The selected option, as returned in a booking_options event")


class BookingConfirmResponse(BaseModel):
    confirmation_code: str
    message: str