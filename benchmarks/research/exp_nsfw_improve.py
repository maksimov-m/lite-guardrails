"""Эксперимент (не трогает прод): NSFW obfuscation-нормализация vs baseline
на AlexSham/Toxic_Russian_Comments (test).

Baseline — точный матч токена по словарю. Improved — на каждый токен генерим
кандидатов (фолдинг латинских гомоглифов -> кириллица, leetspeak, схлопывание
повторов) и баним, если ЛЮБОЙ кандидат в словаре. Оригинал тоже проверяется,
поэтому английские слова не ломаются.

Запуск: PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/exp_nsfw_improve.py
"""

import re
import statistics
import time
import unicodedata

import datasets

from backend.domain.detectors.nsfw import NsfwDetector
from benchmarks.research.bench_external_nsfw import metrics

# латинские буквы, визуально совпадающие с кириллицей -> кириллица
_HOMOGLYPH = str.maketrans({
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х",
    "y": "у", "k": "к", "m": "м", "t": "т", "h": "н", "b": "в",
})
# частые leet-замены -> буквы
_LEET = str.maketrans({
    "0": "о", "3": "з", "4": "ч", "6": "б", "1": "и", "@": "а", "$": "с",
})
_WORD = re.compile(r"[0-9A-Za-zА-Яа-яЁё@$!*]+")
_REPEAT = re.compile(r"(.)\1{2,}")


def _collapse(word: str) -> str:
    return _REPEAT.sub(r"\1", word)


def _candidates(word: str) -> set[str]:
    w = unicodedata.normalize("NFKC", word).lower()
    folded = w.translate(_HOMOGLYPH)
    leet = w.translate(_LEET)
    both = folded.translate(_LEET)
    return {w, folded, leet, both, _collapse(w), _collapse(folded), _collapse(both)}


class NsfwNormalized(NsfwDetector):
    def detect(self, text: str) -> dict:
        found = any(
            self._banned & _candidates(m.group())
            for m in _WORD.finditer(text)
        )
        return {"NSFW_DETECT": found, "data": []}


def evaluate(run, rows):
    pairs, lat = [], []
    for r in rows:
        t0 = time.perf_counter()
        p = run(r["text"])
        lat.append((time.perf_counter() - t0) * 1000)
        pairs.append((bool(r["label"]), p))
    lat.sort()
    return metrics(pairs), {"avg": round(statistics.mean(lat), 4),
                            "p95": round(lat[int(len(lat) * 0.95)], 4)}


def main():
    rows = datasets.load_dataset("AlexSham/Toxic_Russian_Comments", split="test")
    words = NsfwDetector.load_builtin_words()
    base = NsfwDetector(words)
    impr = NsfwNormalized(words)
    base.detect(rows[0]["text"]); impr.detect(rows[0]["text"])  # прогрев

    m0, l0 = evaluate(lambda t: bool(base.detect(t)["NSFW_DETECT"]), rows)
    m1, l1 = evaluate(lambda t: bool(impr.detect(t)["NSFW_DETECT"]), rows)
    print("BASELINE  ", m0, "lat", l0)
    print("NORMALIZED", m1, "lat", l1)


if __name__ == "__main__":
    main()
