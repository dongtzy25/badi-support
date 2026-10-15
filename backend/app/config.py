from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or the .env file."""

    database_url: str = "postgresql+psycopg://badi:badi@localhost:5432/badi_support"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
