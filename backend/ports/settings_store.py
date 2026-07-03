from abc import ABC, abstractmethod


class SettingsStore(ABC):
    """Произвольные рантайм-настройки детекторов (key-value в таблице settings):
    флаги/пороги, которые операторы крутят на лету в админке и которые горячо
    перезагружаются. В отличие от backend.config (env-переменные уровня деплоя),
    это изменяемая на ходу конфигурация. От VersionStore отличается тем, что там
    один счётчик версии, а тут — произвольные ключи."""

    @abstractmethod
    def get(self, key: str, default: str | None = None) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...
