from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user")
    message: str = Field(..., min_length=1, description="The user's chat message")

class ChatResponse(BaseModel):
    reply: str
    memories_used: list[str] = Field(default_factory=list)

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