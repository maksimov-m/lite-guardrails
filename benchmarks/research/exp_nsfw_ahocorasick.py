"""Эксперимент (не трогает прод): Aho-Corasick substring-матч vs baseline
(точный матч токена) на AlexSham/Toxic_Russian_Comments (test).

Вопрос: даёт ли одно-проходный substring-матч по словарю прирост recall
(склейки/вставки) и какой ценой для precision и скорости.

Запуск: PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/exp_nsfw_ahocorasick.py
"""

import statistics
import time

import ahocorasick
import datasets

from backend.domain.detectors.nsfw import NsfwDetector
from benchmarks.research.bench_external_nsfw import metrics


def build_automaton(words):
    a = ahocorasick.Automaton()
    for w in words:
        if w:
            a.add_word(w, w)
    a.make_automaton()
    return a


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
    automaton = build_automaton(words)

    def ac_substring(text):
        low = text.lower()
        for _ in automaton.iter(low):
            return True
        return False

    def _alnum(ch):
        return ch.isalnum()

    def ac_wordbound(text):
        low = text.lower()
        n = len(low)
        for end, word in automaton.iter(low):
            start = end - len(word) + 1
            left_ok = start == 0 or not _alnum(low[start - 1])
            right_ok = end == n - 1 or not _alnum(low[end + 1])
            if left_ok and right_ok:
                return True
        return False

    base.detect(rows[0]["text"]); ac_substring(rows[0]["text"]); ac_wordbound(rows[0]["text"])

    m0, l0 = evaluate(lambda t: bool(base.detect(t)["NSFW_DETECT"]), rows)
    m1, l1 = evaluate(ac_substring, rows)
    m2, l2 = evaluate(ac_wordbound, rows)
    print("BASELINE (exact token)   ", m0, "lat", l0)
    print("AHO-CORASICK (substring) ", m1, "lat", l1)
    print("AHO-CORASICK (word-bound)", m2, "lat", l2)


if __name__ == "__main__":
    main()
