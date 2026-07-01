"""Compute-потолок детекции (in-process, без HTTP/БД).

Честный потолок «сколько детекций в секунду тянет одно ядро» + вклад
недавно добавленной логики (анонимизация-в-лог для pii, auth-хэш ключа).
На Windows+Docker HTTP-числа с хоста упираются в WSL2-прокси, поэтому
compute-потолок меряем прямо здесь.

Запуск:  python benchmarks/compute_bench.py
"""

import hashlib
import json
import time

from src.domain.detectors import NsfwDetector, PiiDetector, RelevantDetector
from src.entrypoints.detectors.log_utils import build_log_payload

# Репрезентативный корпус: чистые/длинные/с PII/чит-чат тексты.
CORPUS = [
    "привет, подскажи как оформить заказ и когда будет доставка",
    "спасибо большое, до свидания, хорошего дня",
    "мой телефон +79161234567, карта 4111111111111111, почта ivan@example.com",
    "нужно уточнить статус, паспорт 4509 123456, снилс 112-233-445 95",
    "это совершенно обычное длинное предложение про погоду и природу вокруг, "
    * 5,
    "ok",
]

ITERS = 30_000


def bench(name, fn):
    # прогрев
    for i in range(1000):
        fn(CORPUS[i % len(CORPUS)])
    start = time.perf_counter()
    for i in range(ITERS):
        fn(CORPUS[i % len(CORPUS)])
    elapsed = time.perf_counter() - start
    per_call_us = elapsed / ITERS * 1e6
    rps = ITERS / elapsed
    print(f"  {name:<34} {rps:>10,.0f} op/s   {per_call_us:>7.2f} µs/op")
    return rps


def main():
    pii = PiiDetector()
    nsfw = NsfwDetector()
    relevant = RelevantDetector()

    print(f"\nCompute-потолок на ОДНО ядро ({ITERS:,} итераций, среднее по корпусу):\n")

    print("Детекторы (чистый detect):")
    r_pii = bench("PII.detect", pii.detect)
    r_nsfw = bench("NSFW.detect", nsfw.detect)
    r_rel = bench("Relevant.detect", relevant.detect)

    print("\nДобавленная нами логика (оверхед на pii-запрос):")
    # полный лог-путь для pii: detect уже сделан, строим payload из результата
    sample = CORPUS[2]
    pii_result = pii.detect(sample)
    bench(
        "build_log_payload(pii)",
        lambda t: build_log_payload("pii", t, pii.detect(t)),
    )
    bench("json.dumps(output)", lambda t: json.dumps(pii_result, ensure_ascii=False))
    bench("auth: sha256(key)", lambda t: hashlib.sha256(t.encode()).hexdigest())

    print("\nЭкстраполяция на воркеры (8 gunicorn-процессов, 12 ядер хоста):")
    for name, r in [("PII", r_pii), ("NSFW", r_nsfw), ("Relevant", r_rel)]:
        print(f"  {name:<10} ~{r * 8:>12,.0f} детекций/с (грубо ×8, если не упрёмся в БД/сеть)")


if __name__ == "__main__":
    main()
