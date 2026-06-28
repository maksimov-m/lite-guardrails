import os
import re

from better_profanity import Profanity

from src.domain.detectors.base import BaseDetector

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class NsfwDetector(BaseDetector):
    """Находит мат/обсценную лексику по готовым словарям (RU + EN).

    Свои слова руками не ведём:
      RU — data/ru_profane_words.txt (~3981) из rominf/profanity-filter
      EN — встроенный словарь better-profanity (+ его leetspeak-варианты)
    Запрещённые слова один раз собираются в set, проверка токена — O(1).
    """

    name = "nsfw"

    # Токены с поддержкой кириллицы и распространённых leet-символов.
    TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё@$!*]+")

    def __init__(self, extra_words=None):
        # builtin-словарь (RU-файл + EN better-profanity) — базовый, всегда вкл.
        # extra_words — кастомные слова из БД (управляются админкой).
        self._banned = self.load_builtin() | {
            w.strip().lower() for w in (extra_words or []) if w.strip()
        }

    @staticmethod
    def load_builtin() -> set:
        path = os.path.join(_DATA_DIR, "ru_profane_words.txt")
        with open(path, encoding="utf-8") as f:
            ru_words = {w.strip().lower() for w in f if w.strip()}

        engine = Profanity()
        engine.load_censor_words()
        return {str(w).lower() for w in engine.CENSOR_WORDSET} | ru_words

    def detect(self, text: str) -> dict:
        data = []
        for token_match in self.TOKEN_RE.finditer(text):
            if token_match.group().lower() in self._banned:
                data.append({
                    "value": token_match.group(),
                    "start": token_match.start(),
                    "end": token_match.end(),
                })

        return {
            "NSFW_DETECT": len(data) > 0,
            "data": data,
        }
