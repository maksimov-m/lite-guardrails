"""Generic CRUD на SQLAlchemy — один класс для всех config-таблиц
(pii/nsfw/relevant/api_keys). Модель и изменяемые поля задаются в конструкторе."""

from sqlalchemy import select

from backend.adapters.db.session import SessionLocal
from backend.ports.crud_repository import CrudRepository


class SqlCrudRepository(CrudRepository):
    """Один generic CRUD на SQLAlchemy — переиспользуется для всех модулей.
    Модель и список изменяемых полей задаются в конструкторе, методы общие."""

    def __init__(self, model, updatable: tuple[str, ...], order_by: tuple = ()):
        self._model = model
        self._updatable = updatable
        self._order_by = order_by or (model.id,)

    def list(self) -> list:
        with SessionLocal() as s:
            return list(s.scalars(select(self._model).order_by(*self._order_by)).all())

    def list_page(self, limit: int, offset: int = 0) -> list:
        with SessionLocal() as s:
            q = (
                select(self._model)
                .order_by(*self._order_by)
                .offset(max(offset, 0))
                .limit(min(limit, 1000))
            )
            return list(s.scalars(q).all())

    def get(self, row_id: int):
        with SessionLocal() as s:
            return s.get(self._model, row_id)

    def find_by(self, field: str, value):
        with SessionLocal() as s:
            return s.scalar(select(self._model).where(getattr(self._model, field) == value))

    def create(self, **fields):
        with SessionLocal() as s:
            row = self._model(**fields)
            s.add(row)
            s.commit()
            return row

    def update(self, row_id: int, fields: dict):
        with SessionLocal() as s:
            row = s.get(self._model, row_id)
            if not row:
                return None
            for name in self._updatable:
                if fields.get(name) is not None:
                    setattr(row, name, fields[name])
            s.commit()
            return row

    def delete(self, row_id: int) -> bool:
        with SessionLocal() as s:
            row = s.get(self._model, row_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            return True
