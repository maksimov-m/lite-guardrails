# lite-guardrails

Самостоятельный сервис-«привратник» для текста на русском: детекция **PII**,
**NSFW** и **релевантности** (смолток/оффтоп) + **анонимизация/деанонимизация** PII.
Не ML-модель, а быстрый детерминированный слой на регулярках и словарях —
разворачивается в своём контуре, конфигурируется через админку, отдаёт метрики и
пробы.

Назначение — дешёвый **первый фильтр** перед LLM/бизнес-логикой: срезать очевидное
(карты, телефоны, СНИЛС, маты, оффтоп) за микросекунды. По скорости на 2–5 порядков
быстрее Presidio/LLM Guard; подробнее — [docs/comparison.md](docs/comparison.md).

## Из чего состоит

- **API + движок** — FastAPI за gunicorn (8 воркеров): детекция, анонимизация,
  админ-CRUD, метрики, пробы.
- **Admin UI** — React + nginx: правила, ключи, логи, дашборд.
- **PostgreSQL** — правила, словари, ключи, логи прогонов, версия конфига (миграции
  Alembic).
- **Redis** — обратимые PII-маппинги (TTL) и счётчики rate limit.

Устройство и связи (C4), справочник ручек и конфигурации —
[docs/architecture.md](docs/architecture.md).

## Как развернуть

Нужен Docker + Docker Compose.

```bash
cp .env.example .env          # заполнить ADMIN_TOKEN и пароли БД
docker compose up -d --build  # api :8000, ui :8080, postgres :5433
```

Миграции и первичный сид накатываются на старте автоматически. Готовность:

```bash
curl localhost:8000/ready     # {"status":"ready"} когда БД и Redis живы
```

- **Admin UI:** http://localhost:8080 — вход по `ADMIN_TOKEN`.
- **API + схема:** http://localhost:8000 · OpenAPI на `/docs`.

### Быстрый старт по API

```bash
# 1. выпустить клиентский ключ (или в UI)
curl -X POST localhost:8000/admin/api-keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"my-app"}'          # -> {"key":"gk_...", ...}

# 2. детекция
curl -X POST localhost:8000/v1/detect/pii \
  -H "X-API-Key: gk_..." -H "Content-Type: application/json" \
  -d '{"text":"мой телефон +79161234567"}'
```

### Python-клиент (SDK)

Вместо сырого HTTP — тонкий клиент [`sdk/python`](sdk/python): подставляет ключ,
делает ретраи, разбирает 401/429 в типизированные ошибки.

```bash
pip install ./sdk/python
```

```python
from lite_guardrails_client import GuardrailsClient, RateLimitError

with GuardrailsClient("http://localhost:8000", api_key="gk_...") as guard:
    out = guard.detect_pii("мой телефон +79161234567")
    if out["PII_DETECT"]:
        ...
    # deanonymize=True — сохранить mapping в Redis для последующего восстановления
    masked = guard.anonymize("почта ivan@example.com", deanonymize=True)
    original = guard.deanonymize(masked["id"], masked["text"])
```

Подробнее (батч, обработка `RateLimitError.retry_after`, все методы) —
[sdk/python/README.md](sdk/python/README.md).

Полный список ручек и переменных `.env` — в [docs/architecture.md](docs/architecture.md).
