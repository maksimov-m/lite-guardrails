"""Нагрузочное тестирование сервиса guard (async httpx).

Заваливает /detect/{module} запросами в N параллельных воркеров в течение
DURATION секунд и считает RPS + перцентили латентности.

Запуск:
  python benchmarks/loadtest.py                       # модуль pii, 64 воркера, 10с
  python benchmarks/loadtest.py --module nsfw --concurrency 128 --duration 15
  python benchmarks/loadtest.py --url http://localhost:8000
"""
import argparse
import asyncio
import time

import httpx

SAMPLES = {
    "pii": "Привет! Мой email maks@gmail.com и телефон 89991330855, сайт example.com",
    "nsfw": "это совершенно обычное и приличное предложение про погоду",
    "relevant": "Расскажи, как устроен механизм газораспределения в двигателе",
}


async def worker(client, url, payload, deadline, lat, count, errors):
    while time.perf_counter() < deadline:
        t0 = time.perf_counter()
        try:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                lat.append((time.perf_counter() - t0) * 1000)
                count[0] += 1
            else:
                errors[0] += 1
        except Exception:
            errors[0] += 1


def pct(sorted_lat, q):
    if not sorted_lat:
        return 0.0
    i = min(len(sorted_lat) - 1, int(q * len(sorted_lat)))
    return sorted_lat[i]


async def run(args):
    url = f"{args.url}/detect/{args.module}"
    payload = {"text": SAMPLES[args.module]}
    lat, count, errors = [], [0], [0]

    limits = httpx.Limits(max_connections=args.concurrency + 10,
                          max_keepalive_connections=args.concurrency + 10)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        # прогрев
        await client.post(url, json=payload)
        deadline = time.perf_counter() + args.duration
        t0 = time.perf_counter()
        await asyncio.gather(*[
            worker(client, url, payload, deadline, lat, count, errors)
            for _ in range(args.concurrency)
        ])
        elapsed = time.perf_counter() - t0

    lat.sort()
    ok = count[0]
    print(f"\nguard load test · {url}")
    print(f"воркеров: {args.concurrency} · длительность: {elapsed:.1f}s\n")
    print(f"  успешных запросов : {ok}")
    print(f"  ошибок            : {errors[0]}")
    print(f"  RPS               : {ok / elapsed:,.0f}")
    print(f"  латентность p50   : {pct(lat, 0.50):.2f} ms")
    print(f"  латентность p90   : {pct(lat, 0.90):.2f} ms")
    print(f"  латентность p99   : {pct(lat, 0.99):.2f} ms")
    print(f"  латентность max   : {lat[-1] if lat else 0:.2f} ms")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--module", default="pii", choices=list(SAMPLES))
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--duration", type=float, default=10.0)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
