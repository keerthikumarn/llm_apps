from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import booking, chat, memory

app = FastAPI(title="AI Travel Agent with Memory", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,   # ← change this line
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(booking.router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}