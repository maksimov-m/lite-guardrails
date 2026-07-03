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

    # Максимальная длина поля text (в символах) в запросах детекции/анонимизации.
    # Больше — запрос отклоняется с 422 ещё до детекции. Защита от DoS большим
    # вводом (relevant/regex растут по длине) и смягчение ReDoS.
    # ~16k символов ≈ 16 КБ ASCII / ~32 КБ кириллицы. Меняется через .env, читается
    # на старте процесса (изменение требует рестарта — как и любой env).
    max_text_length: int = 16384

    # Отдавать метрики в формате Prometheus на GET /metrics. Ручка opt-in для
    # потребителя: если её не скрейпят — ничего не стоит. Выключается флагом.
    metrics_enabled: bool = True

    # Окно, за которое считаются метрики (скользящее). Совпадает по смыслу с
    # дашбордом админки. По умолчанию сутки.
    metrics_window_seconds: int = 86400

    # Кэш ответа /metrics: SQL к run_logs выполняется не чаще, чем раз в N секунд;
    # частые scrape'ы Prometheus отдаются из памяти и не бьют по БД.
    metrics_cache_seconds: float = 15.0

    # Лимит запросов в минуту на API-ключ по умолчанию. Персональный лимит ключа
    # (если задан) переопределяет это значение. <= 0 — без ограничения.
    rate_limit_default_per_min: int = 60

    # Уровень логов приложения (stdout). JSON-формат удобен для ELK/Loki; выключить
    # (log_json=false) — читаемый текст для локального запуска.
    log_level: str = "INFO"
    log_json: bool = True

    # Сколько дней хранить логи прогонов (run_logs). Старше — удаляются фоновой
    # задачей (комплаенс + рост таблицы). <= 0 — не чистить (хранить бессрочно).
    log_retention_days: int = 30

    # CORS. По умолчанию всё открыто ("*") — удобно для внутреннего запуска и
    # разработки. Для prod ужать до своих доменов: задать через env списком
    # (через запятую), напр. CORS_ALLOW_ORIGINS="https://app.company.ru".
    cors_allow_origins: str = "*"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"

    def _csv(self, value: str) -> list[str]:
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items or ["*"]

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return self._csv(self.cors_allow_origins)

    @property
    def cors_allow_methods_list(self) -> list[str]:
        return self._csv(self.cors_allow_methods)

    @property
    def cors_allow_headers_list(self) -> list[str]:
        return self._csv(self.cors_allow_headers)


settings = Settings()
