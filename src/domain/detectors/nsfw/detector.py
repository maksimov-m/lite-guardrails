import os
import re

from src.domain.detectors.base import BaseDetector
from src.domain.detectors.nsfw.utils import build_builtin_words, normalize_words

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class NsfwDetector(BaseDetector):

    name = "nsfw"

    _WORD_PATTERN = re.compile(r"[0-9A-Za-zА-Яа-яЁё@$!*]+")

    def __init__(self, extra_words : list =None):
        self._banned = build_builtin_words(_DATA_DIR) | normalize_words(extra_words)

    def _is_banned(self, word: str) -> bool:
        return word.lower() in self._banned

    def detect(self, text: str) -> dict:
        found = [
            {"value": match.group(), "start": match.start(), "end": match.end()}
            for match in self._WORD_PATTERN.finditer(text)
            if self._is_banned(match.group())
        ]
        return {
            "NSFW_DETECT": len(found) > 0,
            "data": found,
        }
