from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg2://guard:guard@localhost:5432/guard"
    
    redis_url: str = "redis://localhost:6379/0"

    mapping_ttl_seconds: int = 3600

    admin_token: str = "admin"

    # Логировать сырой ввод пользователя (с PII). По умолчанию False —
    # в run_logs пишется анонимизированный текст. Включать только для отладки.
    log_raw_input: bool = False


settings = Settings()
