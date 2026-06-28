from collections import defaultdict

from sqlalchemy import select

from src.adapters.db import Dictionary, Rule, SessionLocal, get_version
from src.domain.detectors import NsfwDetector, PiiDetector, RelevantDetector


class GuardEngine:
    """Держит собранные детекторы и пересобирает их из правил БД (reload).

    Изменения применяются автоматически: каждая правка bump'ает версию, этот
    воркер reload'ится сразу, остальные — фоновым поллером по смене версии.
    """

    def __init__(self):
        self._nsfw_builtin = NsfwDetector.load_builtin_words()
        self._version = -1
        self._pii = self._nsfw = self._relevant = None
        self.reload()

    def reload(self) -> int:
        with SessionLocal() as s:
            rules = s.scalars(select(Rule)).all()
            dicts = s.scalars(select(Dictionary)).all()
            version = get_version()

        # PII: несколько regex на один тег -> склейка через | в один паттерн.
        pii_groups = defaultdict(list)
        for r in rules:
            if r.module == "pii" and r.enabled and r.label:
                pii_groups[r.label.lower()].append(r.value)
        pii_patterns = {
            entity: "|".join(f"(?:{v})" for v in vals)
            for entity, vals in pii_groups.items()
        }

        # NSFW: слова берутся из включённых словарей.
        banned = set()
        enabled_user_dicts = set()
        for d in dicts:
            if not d.enabled:
                continue
            if d.builtin:
                banned |= self._nsfw_builtin
            else:
                enabled_user_dicts.add(d.name)
        for r in rules:
            if r.module == "nsfw" and r.label in enabled_user_dicts:
                banned.add(r.value.strip().lower())

        # relevant: фразы по категориям (несколько на категорию — это норма).
        relevant = defaultdict(list)
        for r in rules:
            if r.module == "relevant" and r.enabled and r.label:
                relevant[r.label].append(r.value)

        self._pii = PiiDetector(patterns=pii_patterns)
        nsfw = NsfwDetector.__new__(NsfwDetector)
        nsfw._banned = banned
        self._nsfw = nsfw
        self._relevant = RelevantDetector(phrases_by_category=dict(relevant))
        self._version = version
        return version

    @property
    def version(self) -> int:
        return self._version

    def detect(self, module: str, text: str) -> dict:
        return {
            "pii": self._pii, "nsfw": self._nsfw, "relevant": self._relevant,
        }[module].detect(text)

    @property
    def pii(self) -> PiiDetector:
        return self._pii
