from abc import ABC, abstractmethod


class VersionStore(ABC):
    """Версия конфига для кросс-воркерного reload: каждая правка её bump'ает,
    поллер сравнивает свою версию с хранилищем и при расхождении перезагружается.
    """

    @abstractmethod
    def get_version(self) -> int: ...

    @abstractmethod
    def bump_version(self) -> int: ...
