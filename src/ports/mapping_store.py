from abc import ABC, abstractmethod


class MappingStore(ABC):
    """Порт хранилища мэппингов анонимизации {тег: оригинал} по ID.

    Конкретные реализации (Redis, in-memory, ...) наследуются от этого класса.
    Меняем бэкенд хранилища — пишем новый подкласс, остальной код не трогаем.
    """

    @abstractmethod
    def save(self, mapping_id: str, mapping: dict) -> None:
        """Сохранить мэппинг под данным ID (реализация решает про TTL)."""

    @abstractmethod
    def get(self, mapping_id: str) -> dict | None:
        """Вернуть мэппинг по ID или None, если его нет/протух."""
