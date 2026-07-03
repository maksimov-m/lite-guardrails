"""HTTP-нагрузка на поднятый сервис.

ВАЖНО (см. заметку по окружению): на Windows+Docker host→container идёт через
WSL2-прокси, поэтому одиночный RPS с хоста обманчиво низкий (~<1k даже на
/health) — это потолок ОКРУЖЕНИЯ, не сервиса. Поэтому:
  - тест A: одиночная латентность /detect (p50/p95) — характеристика пути;
  - тест B: батч-ручка /detect/pii/batch — амортизирует HTTP-оверхед, ближе
    к реальной compute-пропускной;
  - тест C: конкурентный обстрел /detect в N процессов — «пик как есть».

Запуск:  python benchmarks/http_bench.py
"""

import multiprocessing as mp
import statistics
import time

import requests

BASE = "http://localhost:8000"
ADMIN_TOKEN = "admin"
TEXT = "мой телефон +79161234567, карта 4111111111111111, почта ivan@example.com"


def make_key():
    # rate_limit_per_min=0 — без лимита: иначе нагрузка упрётся в 429, а не в сервис.
    r = requests.post(
        f"{BASE}/admin/api-keys",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={"name": "loadtest", "rate_limit_per_min": 0},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["key"]


def test_single_latency(key, n=500):
    h = {"X-API-Key": key}
    lat = []
    for _ in range(n):
        t = time.perf_counter()
        requests.post(f"{BASE}/v1/detect/pii", headers=h, json={"text": TEXT}, timeout=5)
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    print("\n[A] Одиночный /detect/pii (последовательно, 1 соединение):")
    print(f"    n={n}  RPS={n / (sum(lat) / 1000):,.0f}")
    print(f"    p50={lat[n // 2]:.1f}ms  p95={lat[int(n * 0.95)]:.1f}ms  p99={lat[int(n * 0.99)]:.1f}ms")


def test_batch(key, batch_size=500, requests_n=40):
    h = {"X-API-Key": key}
    texts = [TEXT] * batch_size
    # прогрев
    requests.post(f"{BASE}/v1/detect/pii/batch", headers=h, json={"texts": texts}, timeout=30)
    start = time.perf_counter()
    for _ in range(requests_n):
        r = requests.post(f"{BASE}/v1/detect/pii/batch", headers=h, json={"texts": texts}, timeout=30)
        r.raise_for_status()
    elapsed = time.perf_counter() - start
    total = batch_size * requests_n
    print(f"\n[B] Батч /detect/pii/batch ({batch_size} текстов/запрос, {requests_n} запросов):")
    print(f"    {total:,} детекций за {elapsed:.2f}s = {total / elapsed:,.0f} детекций/с (1 соединение)")


def _worker(args):
    key, duration = args
    h = {"X-API-Key": key}
    count = 0
    end = time.perf_counter() + duration
    s = requests.Session()
    while time.perf_counter() < end:
        s.post(f"{BASE}/v1/detect/pii", headers=h, json={"text": TEXT}, timeout=5)
        count += 1
    return count


def test_concurrent(key, procs=12, duration=8):
    print(f"\n[C] Конкурентный /detect/pii: {procs} процессов × {duration}s...")
    with mp.Pool(procs) as pool:
        counts = pool.map(_worker, [(key, duration)] * procs)
    total = sum(counts)
    print(f"    {total:,} запросов за ~{duration}s = {total / duration:,.0f} req/s (пик как есть, env-capped)")


def main():
    assert requests.get(f"{BASE}/health", timeout=5).json()["status"] == "ok"
    key = make_key()
    test_single_latency(key)
    test_batch(key)
    test_concurrent(key)


if __name__ == "__main__":
    main()
