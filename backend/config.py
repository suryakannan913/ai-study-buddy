from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment variables / .env."""

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/studybuddy"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    frontend_origins: str = "http://localhost:3000"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


settings = Settings()
