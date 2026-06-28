from abc import ABC, abstractmethod


class BaseDetector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, text: str) -> dict:
        raise NotImplementedError
