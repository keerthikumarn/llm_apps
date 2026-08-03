from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(payload: ChatRequest) -> ChatResponse:
    try:
        reply, memories_used, intent = chat_service.handle_message(
            user_id = payload.user_id, message = payload.message
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(reply=reply, memories_used=memories_used, intent=intent)


@router.post("/stream")
def send_message_stream(payload: ChatRequest) -> StreamingResponse:
    """
    Streaming counterpart to POST /api/chat. Returns newline-delimited JSON
    events (see ChatService.handle_message_stream for the event shapes)
    instead of a single response body, so the client can render tokens as
    they arrive.
    """
    return StreamingResponse(
        chat_service.handle_message_stream(user_id = payload.user_id, message = payload.message),
        media_type = "application/x-ndjson",
    )