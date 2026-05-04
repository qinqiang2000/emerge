from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite+aiosqlite:///./data/emerge.db")
    jwt_secret: str = Field(default="change-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    storage_root: str = "./data/uploads"

    openai_api_key: str | None = None
    google_api_key: str | None = None
    default_provider: str = "openai"  # 'openai' | 'gemini'
    default_model_openai: str = "gpt-4o-2024-08-06"
    default_model_gemini: str = "gemini-2.0-flash"
    default_model_pro: str = "gemini-3.1-pro-preview"


settings = Settings()
