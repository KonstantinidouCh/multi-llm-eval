from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Multi-LLM Eval"
    debug: bool = False

    # API Keys
    groq_api_key: str = ""
    together_api_key: str = ""
    huggingface_api_key: str = ""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Database
    database_url: str = "sqlite+aiosqlite:///./evaluations.db"

    # MCP Server
    mcp_server_port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
