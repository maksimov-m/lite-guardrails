import os
import re

import ahocorasick

from backend.domain.detectors.base import BaseDetector
from backend.domain.detectors.nsfw.utils import build_builtin_words
from backend.domain.normalization import Normalizer

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Символы, считающиеся частью «слова» (как в прежней токенизации). Совпадение из
# словаря засчитываем только если по обе стороны — не такой символ, т.е. это целый
# токен. Так поведение идентично прежнему точному матчу по токенам, но матчинг
# идёт одним проходом Aho-Corasick (быстрее и масштабируется на большой словарь).
_WORDCHAR = re.compile(r"[0-9A-Za-zА-Яа-яЁё@$!*]")


class NsfwDetector(BaseDetector):
    name = "nsfw"

    def __init__(self, banned: set[str] | None = None):
        self._banned = banned if banned is not None else self.load_builtin_words()
        self._automaton = ahocorasick.Automaton()
        for word in self._banned:
            if word:
                self._automaton.add_word(word, word)
        self._has_words = len(self._automaton) > 0
        if self._has_words:
            self._automaton.make_automaton()

    @staticmethod
    def load_builtin_words() -> set:
        return build_builtin_words(_DATA_DIR)

    @staticmethod
    def _is_wordchar(ch: str) -> bool:
        return bool(_WORDCHAR.match(ch))

    def detect(self, text: str) -> dict:
        text = Normalizer.normalize(text)
        found = []
        if self._has_words:
            last = len(text) - 1
            for end, word in self._automaton.iter(text):
                start = end - len(word) + 1
                left_bound = start == 0 or not self._is_wordchar(text[start - 1])
                right_bound = end == last or not self._is_wordchar(text[end + 1])
                if left_bound and right_bound:
                    found.append({"value": word, "start": start, "end": end + 1})
        return {
            "NSFW_DETECT": len(found) > 0,
            "data": found,
        }
