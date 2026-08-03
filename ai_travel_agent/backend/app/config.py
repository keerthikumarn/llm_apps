from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str = "llama3.2:latest"
    embed_model: str = "nomic-embed-text:latest"
    embed_dims: int = 768

    # Qdrant (vector store used by mem0)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "travel_agent_memory"

    # API
    cors_allow_origins: list[str] = ["*"]  # tighten this in production

    # Chat behavior
    system_prompt: str = (
        "You are a helpful, knowledgeable travel assistant. "
        "Use any relevant past information about the user naturally, "
        "without explicitly mentioning that you are recalling memory."
    )
    memory_search_limit: int = 5
    session_history_max_messages: int = 8


settings = Settings()
