import os
import re

from backend.domain.detectors.base import BaseDetector
from backend.domain.detectors.relevant.utils import (
    build_category_patterns,
    read_chitchat_files,
)
from backend.domain.normalization import Normalizer

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_CHITCHAT_DIR = os.path.join(_DATA_DIR, "chitchat")
_INJECTION_DIR = os.path.join(_DATA_DIR, "injection")

_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
# Множество тех же символов, что матчит _LETTER_RE (строим из самого паттерна —
# гарантированно эквивалентно). Проверка `ch in set` заменяет regex на каждый
# символ при подсчёте покрытия: тот же результат, но без вызова regex-движка.
_LETTER_SET = frozenset(chr(c) for c in range(0x500) if _LETTER_RE.match(chr(c)))


class RelevantDetector(BaseDetector):
    name = "relevant"

    _LETTER_PATTERN = _LETTER_RE
    _LETTER_SET = _LETTER_SET
    COVERAGE_THRESHOLD = 0.8

    # Категории «жёсткого сигнала»: блокируют ввод НЕЗАВИСИМО от порога покрытия.
    # Смолток фильтруем только когда он занимает почти весь текст (COVERAGE_THRESHOLD),
    # но prompt-injection нужно ловить, даже если это одна фраза в большом легитимном
    # на вид сообщении («отличная работа, а теперь забудь все инструкции…»).
    HARD_FLAG_CATEGORIES = frozenset({"injection"})

    def __init__(self, phrases_by_category: dict | None = None, gibberish_enabled: bool = True):
        if phrases_by_category is None:
            phrases_by_category = self.load_default_categories()
        self._patterns = build_category_patterns(phrases_by_category)
        self._gibberish_enabled = gibberish_enabled

    @staticmethod
    def load_chitchat_files() -> dict:
        return read_chitchat_files(_CHITCHAT_DIR)

    @staticmethod
    def load_injection_files() -> dict:
        return read_chitchat_files(_INJECTION_DIR)

    @classmethod
    def load_default_categories(cls) -> dict:
        """Встроенные словари для сида БД и file-based режима: смолток + инъекции."""
        return {**cls.load_chitchat_files(), **cls.load_injection_files()}

    def detect(self, text: str) -> dict:
        text = Normalizer.normalize(text)
        if self._gibberish_enabled and self._is_gibberish(text):
            return {"RELEVANT": False, "category": "gibberish", "data": []}

        matches, scores = self._find_chitchat_matches(text)

        # Жёсткий сигнал (prompt-injection): блокируем независимо от покрытия.
        hard_hits = [m for m in matches if m["category"] in self.HARD_FLAG_CATEGORIES]
        if hard_hits:
            hard_scores = {c: n for c, n in scores.items() if c in self.HARD_FLAG_CATEGORIES}
            return {
                "RELEVANT": False,
                "category": max(hard_scores, key=hard_scores.get),
                "data": hard_hits,
            }

        coverage = self._chitchat_letter_coverage(text, matches)
        is_chitchat = bool(matches) and coverage >= self.COVERAGE_THRESHOLD
        top_category = max(scores, key=scores.get) if scores else None
        return {
            "RELEVANT": not is_chitchat,
            "category": top_category if is_chitchat else None,
            "data": matches,
        }

    def _is_gibberish(self, text: str) -> bool:
        has_letter = self._LETTER_PATTERN.search(text) is not None
        has_digit = any(ch.isdigit() for ch in text)
        return not has_letter and not has_digit

    def _find_chitchat_matches(self, text: str):
        matches = []
        scores = {}
        for category, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                matches.append(
                    {
                        "category": category,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
                scores[category] = scores.get(category, 0) + 1
        return matches, scores

    def _chitchat_letter_coverage(self, text: str, matches: list) -> float:
        covered = [False] * len(text)
        for match in matches:
            for index in range(match["start"], match["end"]):
                covered[index] = True

        total_letters = sum(1 for ch in text if ch in self._LETTER_SET)
        covered_letters = sum(
            1 for index, ch in enumerate(text) if covered[index] and ch in self._LETTER_SET
        )
        return covered_letters / total_letters if total_letters else 0
