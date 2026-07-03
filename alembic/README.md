Alembic — миграции схемы БД (Postgres)
======================================

Здесь живут версии схемы и логика их применения. 

Структура:
  env.py            — бутстрап Alembic; url берётся из DATABASE_URL (см. backend/config.py),
                      а не из alembic.ini. Трогать не нужно.
  script.py.mako    — шаблон, по которому генерируются новые миграции.
  versions/*.py     — сами миграции (линейная цепочка, один head).

Как применяются:
  Автоматически при старте приложения (backend/adapters/migrations.py, под advisory-lock):
  пустая БД -> создать схему; есть версия -> upgrade до head. 

Создать новую миграцию (после правки моделей в backend/adapters/db/models.py):
  1) поднять БД, выставить DATABASE_URL (или .env);
  2) alembic revision --autogenerate -m "краткое описание"
  3) ОТКРЫТЬ сгенерированный versions/*.py и проверить upgrade()/downgrade() — autogenerate
     не идеален (типы, индексы, данные не всегда ловятся);
  4) применится само на следующем старте (или вручную: alembic upgrade head).

Полезное:
  alembic history      — список миграций
  alembic heads        — текущий head (должен быть ОДИН; несколько = ветвление, надо чинить)
  alembic current      — на какой версии сейчас БД

Важно: url для CLI берётся из DATABASE_URL через env.py — переопределять через alembic.ini
или -x бесполезно, меняйте DATABASE_URL.

Документация: https://alembic.sqlalchemy.org/en/latest/
