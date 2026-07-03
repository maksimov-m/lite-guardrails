# Архитектура

C4-описание системы (Context → Container → Component) плюс справочник ручек,
конфигурации и мониторинга. Как развернуть — см. [Развёртывание](deployment.md).

## Уровень 1 — контекст

```mermaid
C4Context
  Person(client, "Клиентское приложение", "чат-бот, бэкенд платформы")
  Person(admin, "Администратор", "настраивает правила и ключи")
  System(guard, "lite-guardrails", "Детекция PII/NSFW/relevance + анонимизация")
  System_Ext(prom, "Prometheus / Grafana", "мониторинг")

  Rel(client, guard, "POST /v1/detect/*, /v1/anonymize", "HTTPS + X-API-Key")
  Rel(admin, guard, "правила, ключи, логи", "Admin UI / X-Admin-Token")
  Rel(prom, guard, "scrape GET /metrics", "HTTP")
```

## Уровень 2 — контейнеры

```mermaid
C4Container
  Person(client, "Клиент", "API-key")
  Person(admin, "Админ", "admin-token")

  System_Boundary(sys, "lite-guardrails") {
    Container(api, "API + движок", "Python, FastAPI, gunicorn (8 воркеров)", "детекция, анонимизация, админ-CRUD, метрики, пробы")
    Container(ui, "Admin UI", "React + nginx", "правила, ключи, логи, дашборд")
    ContainerDb(pg, "PostgreSQL", "SQLAlchemy + Alembic", "правила, словари, ключи, run_logs, версия конфига")
    ContainerDb(redis, "Redis", "", "PII-маппинги (TTL) + счётчики rate limit")
  }

  Rel(client, api, "POST /v1/*", "HTTPS")
  Rel(admin, ui, "использует", "браузер")
  Rel(ui, api, "проксирует /v1, /admin", "nginx")
  Rel(api, pg, "конфиг + запись логов пачками", "psycopg2")
  Rel(api, redis, "маппинги, rate limit", "redis-py")
```

## Уровень 3 — компоненты API (ports & adapters)

```mermaid
C4Component
  Container_Boundary(api, "API + движок") {
    Component(routers, "Entrypoints", "FastAPI routers", "detect/anonymize (/v1), admin, /metrics, /live /ready /health")
    Component(auth, "Auth + Rate limit", "dependency", "X-API-Key + лимит per-key")
    Component(engine, "GuardEngine", "domain", "держит детекторы, hot-reload по версии конфига")
    Component(detectors, "Детекторы", "domain", "PII (regex+Luhn), NSFW (словарь), Relevant")
    Component(runlog, "RunLogger", "async", "очередь + батч-запись логов, PII-safe")
    Component(ports, "Ports", "интерфейсы", "Crud / RunLog / Version / MappingStore / RateLimiter")
  }
  ContainerDb(pg, "PostgreSQL", "", "")
  ContainerDb(redis, "Redis", "", "")

  Rel(routers, auth, "проверяет запрос")
  Rel(routers, engine, "detect(text)")
  Rel(engine, detectors, "прогон")
  Rel(routers, runlog, "log() (неблокирующе)")
  Rel(auth, redis, "INCR лимита", "через RateLimiter")
  Rel(runlog, pg, "bulk insert", "через RunLog-порт")
  Rel(engine, pg, "reload конфига", "через Crud/Version-порты")
```

## Ключевые решения

- **Ports & adapters** — домен (детекторы) не знает про БД/Redis; смена хранилища =
  новый адаптер, остальной код не трогается.
- **Hot-path не блокирует БД:** детекция — в памяти; запись лога — в очередь +
  фоновый батч в отдельном потоке (`asyncio.to_thread`); блокирующие вызовы (stats,
  метрики, rate limit) уходят в threadpool, не в event loop.
- **Hot-reload конфига:** правка в админке поднимает версию конфига, воркеры
  перечитывают его фоновым поллером — без рестарта.
- **PII не попадает в stdout-логи:** в `run_logs` пишется анонимизированный текст,
  в access-лог — только метаданные (метод/статус/длительность/ключ). Сквозной
  `request-id` для корреляции.
- **Rate limit:** конфиг лимита — в Postgres (колонка у ключа, кэшируется в память),
  счётчики — в Redis (fixed-window, общий на все воркеры); при недоступности Redis
  fail-open.

Справочник ручек, переменных `.env` и мониторинга — в разделе
[Развёртывание](deployment.md).
