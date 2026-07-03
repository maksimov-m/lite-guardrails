"""Ключи и хелперы рантайм-настроек детекторов (хранятся в таблице settings,
редактируются в админке, горячо перезагружаются движком).

В отличие от backend.config (env-переменные уровня деплоя) — это то, что
операторы меняют на лету. Значения в БД хранятся строками ("1"/"0" для флагов),
здесь — типобезопасная обёртка над SettingsStore.
"""

from backend.ports.settings_store import SettingsStore

# relevant: включён ли этап детекции «мусора» (gibberish — текст без букв и цифр).
# Дефолт — включён; оператор может отключить, если junk-ввод для его кейса
# считается допустимым.
RELEVANT_GIBBERISH_ENABLED = "relevant_gibberish_enabled"

# Дефолты на случай отсутствия строки в БД (свежая/недосиженная база).
DEFAULTS: dict[str, bool] = {
    RELEVANT_GIBBERISH_ENABLED: True,
}


def get_bool(store: SettingsStore, key: str) -> bool:
    raw = store.get(key)
    if raw is None:
        return DEFAULTS.get(key, False)
    return raw == "1"


def set_bool(store: SettingsStore, key: str, value: bool) -> None:
    store.set(key, "1" if value else "0")
