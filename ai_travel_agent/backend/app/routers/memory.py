from fastapi import APIRouter, HTTPException

from app.schemas import DeleteMemoryResponse, MemoryItem, MemoryListResponse
from app.services.memory_service import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/{user_id}", response_model=MemoryListResponse)
def get_memories(user_id: str) -> MemoryListResponse:
    try:
        raw = memory_service.get_all(user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items = [
        MemoryItem(id=m.get("id"), memory=m.get("memory", ""), metadata=m.get("metadata"))
        for m in raw
    ]
    return MemoryListResponse(user_id=user_id, memories=items)


@router.delete("/{user_id}", response_model=DeleteMemoryResponse)
def delete_memories(user_id: str) -> DeleteMemoryResponse:
    try:
        memory_service.delete_all(user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DeleteMemoryResponse(user_id=user_id, deleted=True)