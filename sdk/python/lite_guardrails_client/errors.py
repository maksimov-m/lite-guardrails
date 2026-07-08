"""Типизированные ошибки клиента."""

from __future__ import annotations


class GuardrailsError(Exception):
    """Базовая ошибка клиента."""


class AuthError(GuardrailsError):
    """Невалидный или отсутствующий API-ключ (HTTP 401)."""


class RateLimitError(GuardrailsError):
    """Превышен лимит запросов (HTTP 429). retry_after — секунд до сброса окна."""

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class APIError(GuardrailsError):
    """Прочая ошибка API/транспорта. status_code — код ответа, если был."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
