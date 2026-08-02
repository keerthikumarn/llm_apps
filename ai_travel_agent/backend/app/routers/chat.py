from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(payload: ChatRequest) -> ChatResponse:
    try:
        reply, memories_used = chat_service.handle_message(
            user_id=payload.user_id, message=payload.message
        )
    except Exception as exc:  # noqa: BLE001 - surface as a clean 500 to the client
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(reply=reply, memories_used=memories_used)


@router.post("/stream")
def send_message_stream(payload: ChatRequest) -> StreamingResponse:
    """
    Streaming counterpart to POST /api/chat.
    """
    return StreamingResponse(
        chat_service.handle_message_stream(user_id=payload.user_id, message=payload.message),
        media_type="application/x-ndjson",
    )