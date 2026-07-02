"""cProfile хот-пути детекции (in-process) для поиска bottleneck'ов.

Профилируем самый тяжёлый путь — /detect/pii с логированием: detect() +
build_log_payload() (анонимизация из спанов) + json.dumps(). HTTP/БД исключены
намеренно — их вклад меряется отдельно (см. http_bench.py), а тут ищем, что
жрёт CPU в самой обработке.

Запуск:  python benchmarks/profile_hotpath.py [pii|nsfw|relevant]
"""

import cProfile
import json
import pstats
import sys

from backend.domain.detectors import NsfwDetector, PiiDetector, RelevantDetector
from backend.entrypoints.detectors.log_utils import build_log_payload

CORPUS = [
    "мой телефон +79161234567, карта 4111111111111111, почта ivan@example.com",
    "привет, подскажи как оформить заказ и когда будет доставка сегодня",
    "спасибо большое, до свидания, хорошего дня",
    "это совершенно обычное длинное предложение про погоду и природу вокруг, " * 5,
]

ITERS = 50_000


def make_detector(module):
    return {"pii": PiiDetector, "nsfw": NsfwDetector, "relevant": RelevantDetector}[module]()


def hot_path(detector, module):
    for i in range(ITERS):
        text = CORPUS[i % len(CORPUS)]
        result = detector.detect(text)
        log_text, log_output = build_log_payload(module, text, result)
        json.dumps(log_output, ensure_ascii=False)


def main():
    module = sys.argv[1] if len(sys.argv) > 1 else "pii"
    detector = make_detector(module)

    print(f"\nПрофилирование хот-пути module={module}, {ITERS:,} итераций...\n")
    profiler = cProfile.Profile()
    profiler.enable()
    hot_path(detector, module)
    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.sort_stats("tottime")
    print("Топ-15 по собственному времени (tottime):")
    stats.print_stats(15)


if __name__ == "__main__":
    main()
