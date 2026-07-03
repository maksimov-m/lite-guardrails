"""Эксперимент (не трогает прод): улучшения PII vs baseline на hivetrace/pii-bench.

Проверяем два изменения на слабых местах baseline:
  - SNILS: разрешить форму без разделителей (regex с опциональными [\\s-]);
           контрольная сумма оставлена — precision не должна упасть.
  - bank_card: вариант без Луна (pattern-only) — ловим синтетические карты
           бенчмарка; смотрим, насколько падает precision.

Запуск: PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/exp_pii_improve.py
"""

import json

import datasets

from backend.domain.detectors.pii.detector import PiiDetector
from backend.domain.detectors.pii.patterns import (
    EmailPattern,
    InnPattern,
    IpPattern,
    PassportRfPattern,
    PhonePattern,
    UrlPattern,
)
from backend.domain.detectors.pii.patterns.bank_card import BankCardPattern
from backend.domain.detectors.pii.patterns.snils import SnilsPattern
from benchmarks.research.bench_external_pii import OURS_TO_CANON, score


class SnilsBroad(SnilsPattern):
    # разделители опциональны -> ловим и "12345678901", контрольную сумму храним
    regex = r"(?<!\d)\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}(?!\d)"


class BankCardNoLuhn(BankCardPattern):
    def is_valid(self, value: str) -> bool:  # только паттерн, без Луна
        return True


def _detector(patterns):
    det = PiiDetector()
    det._patterns = patterns
    return det


def _runner(det):
    def run(text):
        out = det.detect(text)
        return [
            (d["start"], d["end"], OURS_TO_CANON[d["class"]])
            for d in out["data"] if d["class"] in OURS_TO_CANON
        ]
    return run


def _print(title, res):
    print(f"\n=== {title} ===")
    print("micro:", json.dumps(res["micro"], ensure_ascii=False), "| lat:", res["latency_ms"])
    for t, v in res["per_type"].items():
        print(f"  {t:<10} P={v['precision']:.2f} R={v['recall']:.2f} F1={v['f1']:.2f} (n={v['support']})")


def main():
    ds = datasets.load_dataset("hivetrace/pii-bench")
    rows = [(r["text"], r["entities"]) for split in ds.values() for r in split]

    baseline = _detector([
        EmailPattern(), UrlPattern(), PhonePattern(), BankCardPattern(),
        SnilsPattern(), InnPattern(), PassportRfPattern(), IpPattern(),
    ])
    improved = _detector([
        EmailPattern(), UrlPattern(), PhonePattern(), BankCardNoLuhn(),
        SnilsBroad(), InnPattern(), PassportRfPattern(), IpPattern(),
    ])

    rb = _runner(baseline)
    ri = _runner(improved)
    rb(rows[0][0]); ri(rows[0][0])  # прогрев

    _print("BASELINE", score(rows, rb, supported_only=True))
    _print("IMPROVED (snils broad + bank_card no-Luhn)", score(rows, ri, supported_only=True))


if __name__ == "__main__":
    main()
