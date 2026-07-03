from collections import defaultdict

from backend.domain.detectors import NsfwDetector, PiiDetector, RelevantDetector
from backend.domain.detectors.nsfw.utils import normalize_words
from backend.ports.crud_repository import CrudRepository
from backend.ports.settings_store import SettingsStore
from backend.ports.version_store import VersionStore
from backend.runtime_settings import RELEVANT_GIBBERISH_ENABLED, get_bool


class GuardEngine:
    """Держит собранные детекторы и пересобирает их из конфига (reload).

    Конфиг читается через порты-репозитории — движок не знает, какая под ним
    БД. Изменения применяются автоматически: каждая правка bump'ает версию,
    этот воркер reload'ится сразу, остальные — фоновым поллером по смене версии.
    """

    def __init__(
        self,
        pii_repo: CrudRepository,
        nsfw_repo: CrudRepository,
        relevant_repo: CrudRepository,
        version_store: VersionStore,
        settings_store: SettingsStore | None = None,
    ):
        self._pii_repo = pii_repo
        self._nsfw_repo = nsfw_repo
        self._relevant_repo = relevant_repo
        self._version_store = version_store
        self._settings_store = settings_store
        self._version = -1
        self._pii = self._nsfw = self._relevant = None
        self.detectors = None
        self.reload()

    def reload(self) -> int:
        self._pii = self._build_pii(self._pii_repo.list())
        self._nsfw = self._build_nsfw(self._nsfw_repo.list())
        self._relevant = self._build_relevant(
            self._relevant_repo.list(), self._relevant_gibberish_enabled()
        )
        self._version = self._version_store.get_version()
        self.detectors = {
            "pii": self._pii,
            "nsfw": self._nsfw,
            "relevant": self._relevant,
        }
        return self._version

    @staticmethod
    def _build_pii(pii_rules) -> PiiDetector:
        regexes_by_type = defaultdict(list)
        for rule in pii_rules:
            if rule.enabled and rule.type:
                regexes_by_type[rule.type.lower()].append(rule.regex)
        patterns = {
            entity: "|".join(f"(?:{regex})" for regex in regexes)
            for entity, regexes in regexes_by_type.items()
        }
        return PiiDetector(patterns=patterns)

    @staticmethod
    def _build_nsfw(nsfw_dicts) -> NsfwDetector:
        banned = set()
        for dictionary in nsfw_dicts:
            if dictionary.enabled:
                banned |= normalize_words(dictionary.text.split())
        return NsfwDetector(banned)

    def _relevant_gibberish_enabled(self) -> bool:
        # Нет settings-store (напр. в узких юнит-тестах) — дефолт: этап включён.
        if self._settings_store is None:
            return True
        return get_bool(self._settings_store, RELEVANT_GIBBERISH_ENABLED)

    @staticmethod
    def _build_relevant(relevant_cats, gibberish_enabled: bool = True) -> RelevantDetector:
        phrases_by_category = {}
        for category in relevant_cats:
            if category.enabled and category.type:
                phrases = [line for line in category.text.splitlines() if line.strip()]
                if phrases:
                    phrases_by_category[category.type] = phrases
        return RelevantDetector(
            phrases_by_category=phrases_by_category, gibberish_enabled=gibberish_enabled
        )

    @property
    def version(self) -> int:
        return self._version

    def detect(self, module: str, text: str) -> dict:
        result = self.detectors[module].detect(text)
        return result

    @property
    def pii(self) -> PiiDetector:
        return self._pii
