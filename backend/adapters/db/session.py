"""Подключение к БД: engine и фабрика сессий (общие для всех репозиториев)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
