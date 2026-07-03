// Типизированные ошибки клиента (зеркалят Python SDK).

export class GuardrailsError extends Error {
  constructor(message) {
    super(message);
    this.name = "GuardrailsError";
  }
}

/** Невалидный или отсутствующий API-ключ (HTTP 401). */
export class AuthError extends GuardrailsError {
  constructor(message) {
    super(message);
    this.name = "AuthError";
  }
}

/** Превышен лимит запросов (HTTP 429). retryAfter — секунд до сброса окна. */
export class RateLimitError extends GuardrailsError {
  constructor(message, retryAfter = 0) {
    super(message);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}

/** Прочая ошибка API/транспорта. statusCode — код ответа, если был. */
export class APIError extends GuardrailsError {
  constructor(message, statusCode = null) {
    super(message);
    this.name = "APIError";
    this.statusCode = statusCode;
  }
}
