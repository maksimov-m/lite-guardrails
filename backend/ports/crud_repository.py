from abc import ABC, abstractmethod
from typing import Any


class CrudRepository(ABC):
    """CRUD над одним видом сущностей конфига.

    Один и тот же набор команд для всех модулей — для PII-правил, NSFW-словарей
    и relevant-категорий заводится по своему репозиторию с этим интерфейсом.
    Возвращаемые «строки» — объекты с атрибутами соответствующей сущности
    (напр. PII: .id/.type/.regex/.enabled).
    """

    @abstractmethod
    def list(self) -> list[Any]:
        """Все записи (в стабильном для UI порядке)."""

    @abstractmethod
    def get(self, row_id: int) -> Any | None:
        """Запись по id или None."""

    @abstractmethod
    def find_by(self, field: str, value: Any) -> Any | None:
        """Первая запись с field == value или None (для проверки уникальности)."""

    @abstractmethod
    def create(self, **fields: Any) -> Any:
        """Создать запись из переданных полей и вернуть её."""

    @abstractmethod
    def update(self, row_id: int, fields: dict) -> Any | None:
        """Обновить запись присутствующими полями (None-значения пропускаются)."""

    @abstractmethod
    def delete(self, row_id: int) -> bool:
        """Удалить запись; True если была, False если не нашлась."""
