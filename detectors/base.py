from abc import ABC, abstractmethod


class BaseDetector(ABC):
    """Единый интерфейс детектора.

    Все детекторы наследуются от этого класса: на вход — текст,
    на выходе — словарь-результат (своя структура у каждого детектора).
    """

    #: короткое имя детектора (pii / nsfw / relevant)
    name: str = "base"

    @abstractmethod
    def detect(self, text: str) -> dict:
        """Проанализировать текст и вернуть результат детекции."""
        raise NotImplementedError
