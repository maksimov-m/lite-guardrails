FROM python:3.12-slim

WORKDIR /app

# Зависимости отдельным слоем — кешируются, пока requirements.txt не менялся.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код и словари детекторов.
COPY detectors ./detectors
COPY app.py store.py db.py engine.py admin.py runlog.py ./

EXPOSE 8000

# gunicorn + UvicornWorker => uvloop и httptools включаются автоматически
# (благодаря uvicorn[standard]). Число воркеров регулируется env WORKERS.
CMD gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    --workers ${WORKERS:-8} \
    --bind 0.0.0.0:8000 \
    --log-level warning
