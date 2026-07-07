# Мониторинг (Prometheus + Grafana)

Опциональный стек наблюдаемости. Поднимается **только** под профилем `monitoring`
— базовый `docker compose up` его не тянет.

## Запуск

```bash
docker compose --profile monitoring up -d
```

- **Grafana** — <http://localhost:3000>: дашборд «lite-guardrails · обзор» уже
  загружен (запросы/детекции по модулям, доля срабатываний). Просмотр анонимный;
  правка — под `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` из `.env`.
- **Prometheus** — <http://localhost:9090>. Оба порта слушают только `127.0.0.1`.

Остановить только мониторинг: `docker compose stop prometheus grafana`.

Кому свой стек сбора — можно профиль не включать и просто скрейпить `GET /metrics`
сервиса (метрики отдаются в формате Prometheus).

## Что за файлы

```
monitoring/
├── prometheus/
│   └── prometheus.yml                     # scrape-конфиг: тянет /metrics с guardrails:8000
└── grafana/
    ├── provisioning/                      # автонастройка Grafana при старте
    │   ├── datasources/datasource.yml     # подключает Prometheus как источник данных
    │   └── dashboards/dashboards.yml       # провайдер: откуда грузить дашборды
    └── dashboards/
        └── lite-guardrails.json           # сам дашборд (панели под метрики /metrics)
```

Всё подхватывается автоматически (provisioning) — руками в UI ничего настраивать
не нужно. Правки конфигов применяются после `docker compose --profile monitoring
up -d` (перезапуск сервисов).

## Примечание про метрики

`/metrics` отдаёт значения типа **gauge** за скользящее окно `METRICS_WINDOW_SECONDS`
(по умолчанию сутки), а не монотонные счётчики — то есть значение уже равно числу
за окно. Латентности в `/metrics` нет (она есть в админ-дашборде сервиса). Дашборд
построен именно под то, что реально экспортируется.
