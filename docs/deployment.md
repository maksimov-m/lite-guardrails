# Развёртывание

Нужен Docker + Docker Compose.

```bash
cp .env.example .env          # заполнить ADMIN_TOKEN и пароли БД
docker compose up -d --build  # ui :8080, api :8000 (localhost), postgres :5433
```

Миграции и первичный сид накатываются на старте автоматически (под advisory-lock,
один воркер). Проверка готовности:

```bash
curl localhost:8000/ready     # {"status":"ready"} когда БД и Redis живы
```

- **Admin UI:** [http://localhost:8080](http://localhost:8080) — вход по `ADMIN_TOKEN`.
- **API напрямую:** [http://localhost:8000](http://localhost:8000) — обычный FastAPI,
  Swagger на `/docs`, ReDoc на `/redoc`. Порт слушает только `127.0.0.1`; открыть
  по сети — правьте `ports` в `docker-compose.yml`.
- **Единая точка входа:** [http://localhost:8080](http://localhost:8080) — nginx
  проксирует API (`/v1`, `/admin`) и схему (`/docs`) на тот же origin. Для прод-контура
  публикуйте только его (за TLS), порт `:8000` можно закрыть.

## Быстрый старт по API

```bash
# 1. выпустить клиентский ключ (или в админке)
curl -X POST localhost:8000/admin/api-keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"my-app"}'          # -> {"key":"gk_...", ...}

# 2. детекция
curl -X POST localhost:8000/v1/detect/pii \
  -H "X-API-Key: gk_..." -H "Content-Type: application/json" \
  -d '{"text":"мой телефон +79161234567"}'
```

Интеграция из кода — см. [Python SDK](sdk.md).

## Ручки

| Группа | Пути | Авторизация |
|---|---|---|
| Детекция | `POST /v1/detect/{pii,nsfw,relevant}` (+`/batch`) | `X-API-Key` |
| Анонимизация | `POST /v1/{anonymize,deanonymize}` (+`/batch`) | `X-API-Key` |
| Админка | `GET/POST/PATCH/DELETE /admin/*` | `X-Admin-Token` |
| Инфра | `GET /metrics` · `/live` · `/ready` · `/health` | нет (защита на ingress) |

Публичный контракт версионирован (`/v1`); инфраструктурные ручки — вне версии.

## Конфигурация (`.env`)

| Переменная | Назначение | Дефолт |
|---|---|---|
| `DATABASE_URL` | DSN PostgreSQL | — |
| `REDIS_URL` | подключение Redis | — |
| `ADMIN_TOKEN` | токен админ-ручек | — (обязательно сменить) |
| `WORKERS` | число gunicorn-воркеров | 8 |
| `RATE_LIMIT_DEFAULT_PER_MIN` | лимит на ключ по умолчанию (0 — без лимита) | 60 |
| `LOG_RETENTION_DAYS` | сколько дней хранить логи прогонов (0 — бессрочно) | 30 |
| `MAPPING_TTL_SECONDS` | TTL PII-маппингов в Redis | 3600 |
| `LOG_LEVEL` / `LOG_JSON` | уровень и формат stdout-логов | INFO / true |
| `METRICS_ENABLED` | отдавать `/metrics` | true |

## Мониторинг и пробы

`GET /metrics` — метрики Prometheus (запросы/детекции по модулям, скользящее
окно `METRICS_WINDOW_SECONDS`, тип gauge). Сам сервис ничего не собирает — это
пассивный источник в pull-модели: если никто не скрейпит, ручка ничего не стоит.

Стек сбора опционален. Три сценария:

**1. Готовый стек одной командой (профиль `monitoring`).** В `docker-compose.yml`
есть сервисы `prometheus` и `grafana` под профилем `monitoring` — без профиля они
не поднимаются. С профилем поднимается всё вместе, Grafana сама подхватывает
источник данных и дашборд (автопровижининг из `monitoring/`):

```bash
docker compose --profile monitoring up -d
```

- Grafana: <http://localhost:3000> (дашборд «lite-guardrails · обзор» уже загружен;
  просмотр анонимный, правка — под `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`).
- Prometheus: <http://localhost:9090>. Оба порта висят только на `127.0.0.1`.
- Конфиги правятся в `monitoring/prometheus/` и `monitoring/grafana/`.

**2. Свой Prometheus.** Профиль не включаем — просто скрейпим ручку своим стеком:

```yaml
scrape_configs:
  - job_name: lite-guardrails
    static_configs: [{ targets: ["guardrails:8000"] }]
```

**3. Никакого мониторинга.** Не делаем ничего — базовый `docker compose up`
Prometheus/Grafana не тянет.

Пробы оркестратора: `livenessProbe` → `/live` (только «процесс жив» — провал
перезапускает под), `readinessProbe` → `/ready` (проверяет Postgres + Redis —
провал убирает под из балансировки без рестарта).

## TLS

Сервис слушает HTTP. В проде ставьте его за TLS-терминирующим слоем
(ingress-контроллер, nginx, балансировщик) — приложение остаётся на HTTP внутри
доверенной сети, шифрование снимается на границе.
