import os
import re

from src.domain.detectors.base import BaseDetector
from src.domain.detectors.relevant.utils import (
    build_category_patterns,
    read_chitchat_files,
)

_CHITCHAT_DIR = os.path.join(os.path.dirname(__file__), "data", "chitchat")


class RelevantDetector(BaseDetector):

    name = "relevant"

    _LETTER_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]")
    COVERAGE_THRESHOLD = 0.8

    def __init__(self, phrases_by_category: dict | None = None):
        if phrases_by_category is None:
            phrases_by_category = self.load_chitchat_files()
        self._patterns = build_category_patterns(phrases_by_category)

    @staticmethod
    def load_chitchat_files() -> dict:
        return read_chitchat_files(_CHITCHAT_DIR)

    def detect(self, text: str) -> dict:
        if self._is_gibberish(text):
            return {"RELEVANT": False, "category": "gibberish", "data": []}

        matches, scores = self._find_chitchat_matches(text)
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
                matches.append({
                    "category": category,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })
                scores[category] = scores.get(category, 0) + 1
        return matches, scores

    def _chitchat_letter_coverage(self, text: str, matches: list) -> float:
        covered = [False] * len(text)
        for match in matches:
            for index in range(match["start"], match["end"]):
                covered[index] = True

        total_letters = sum(1 for ch in text if self._LETTER_PATTERN.match(ch))
        covered_letters = sum(
            1 for index, ch in enumerate(text)
            if covered[index] and self._LETTER_PATTERN.match(ch)
        )
        return covered_letters / total_letters if total_letters else 0
