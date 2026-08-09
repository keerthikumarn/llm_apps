from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model = ChatResponse)
def send_message(payload: ChatRequest) -> ChatResponse:
    try:
        reply, memories_used, intent, suggestions = chat_service.handle_message(
            user_id = payload.user_id, message = payload.message, agent = payload.agent
        )
    except Exception as exc:
        raise HTTPException(status_code = 500, detail = str(exc)) from exc

    return ChatResponse(reply = reply, memories_used = memories_used, intent = intent, suggestions = suggestions)


@router.post("/stream")
def send_message_stream(payload: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        chat_service.handle_message_stream(
            user_id = payload.user_id, message = payload.message, agent = payload.agent
        ),
        media_type = "application/x-ndjson",
    )