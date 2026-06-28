FROM python:3.12-slim

WORKDIR /app

# Зависимости отдельным слоем — кешируются, пока requirements.txt не менялся.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Весь код — пакет src (domain / adapters / entrypoints). litellm_middleware
# исключён через .dockerignore (он для отдельного LiteLLM-прокси, не для гуарда).
COPY src ./src

# src импортируется как пакет (from src.entrypoints.app ...), поэтому корнем
# путей делаем /app.
ENV PYTHONPATH=/app

EXPOSE 8000

# gunicorn + UvicornWorker => uvloop и httptools включаются автоматически
# (благодаря uvicorn[standard]). Число воркеров регулируется env WORKERS.
CMD gunicorn src.entrypoints.app:app \
    -k uvicorn.workers.UvicornWorker \
    --workers ${WORKERS:-8} \
    --bind 0.0.0.0:8000 \
    --log-level warning
