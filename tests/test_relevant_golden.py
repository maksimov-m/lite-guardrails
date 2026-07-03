"""Golden-тест эквивалентности RelevantDetector.

Эталон (relevant_golden.json) снят на коде ДО оптимизации letter-coverage.
Тест гарантирует, что оптимизация не меняет выход детектора ни на одном
из текстов корпуса (специально нагружает подсчёт покрытия буквами:
разные доли покрытия, регистр, ёЁ, латиница+кириллица, цифры, gibberish, пустое).

Пере-снять эталон (только осознанно!):  PYTHONPATH=. python tests/test_relevant_golden.py
"""

import json
import os

from backend.domain.detectors import RelevantDetector

GOLDEN = os.path.join(os.path.dirname(__file__), "data", "relevant_golden.json")

CORPUS = [
    "привет, спасибо большое, до свидания",
    "здравствуйте! добрый день",
    "спасибо! хорошего дня, пока",
    "привет, подскажи статус заказа 12345",
    "спасибо, а когда будет доставка на следующей неделе",
    "нужно уточнить условия возврата товара и сроки",
    "как подключить интеграцию по api к вашему сервису",
    "ПРИВЕТ, СПАСИБО, всё отлично, ещё раз спасибо",
    "приёмная, ёлка, объём, съезд",
    "hello привет thanks спасибо bye пока",
    "заказ №12345, оплата 4999 руб., спасибо!!!",
    "   ",
    "",
    "!!! ??? ... ,,, ",
    "1234567890",
    "это совершенно обычное длинное предложение про погоду и природу вокруг, " * 4,
    "спасибо большое хорошего дня до свидания всего доброго " * 4,
    "спасибо",
    "asdqwe",
    "ok",
]


def _compute():
    det = RelevantDetector()
    return [det.detect(t) for t in CORPUS]


def test_relevant_output_matches_golden():
    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    actual = _compute()

    # Поэлементно: при расхождении сразу видно, НА КАКОМ тексте разъехался
    # выход, а не безликое «списки не равны».
    assert len(actual) == len(golden), "изменился размер корпуса — пересними эталон"
    for text, got, want in zip(CORPUS, actual, golden):
        assert got == want, f"relevant изменился на {text!r}:\n  получили {got}\n  эталон  {want}"


if __name__ == "__main__":
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(_compute(), f, ensure_ascii=False, indent=2)
    print(f"saved {len(CORPUS)} results -> {GOLDEN}")
