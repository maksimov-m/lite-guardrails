"""Многопроцессный драйвер нагрузки (обходит GIL одного процесса).

Запускает PROCS процессов, в каждом — CONC async-воркеров, и агрегирует RPS.
Нужен, потому что один python-процесс с asyncio+httpx упирается в GIL и не
выдаёт реальный потолок сервера.

Запуск:
  python benchmarks/loadtest_mp.py --path /health --procs 8 --conc 64 --duration 10
  python benchmarks/loadtest_mp.py --path /detect/nsfw --method POST --procs 8 --conc 64
"""
import argparse
import asyncio
import multiprocessing as mp
import time

import httpx

PAYLOAD = {"text": "обычное приличное предложение про погоду и природу"}


async def _workers(base, path, method, conc, duration, q):
    lat, cnt, err = [], 0, 0
    url = base + path
    lim = httpx.Limits(max_connections=conc + 10, max_keepalive_connections=conc + 10)
    async with httpx.AsyncClient(timeout=30, limits=lim) as c:
        async def one(deadline):
            nonlocal cnt, err
            while time.perf_counter() < deadline:
                t = time.perf_counter()
                try:
                    r = (await c.post(url, json=PAYLOAD) if method == "POST"
                         else await c.get(url))
                    if r.status_code == 200:
                        lat.append((time.perf_counter() - t) * 1000); cnt += 1
                    else:
                        err += 1
                except Exception:
                    err += 1
        dl = time.perf_counter() + duration
        await asyncio.gather(*[one(dl) for _ in range(conc)])
    q.put((cnt, err, lat))


def _proc(base, path, method, conc, duration, q):
    asyncio.run(_workers(base, path, method, conc, duration, q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--path", default="/health")
    ap.add_argument("--method", default="GET", choices=["GET", "POST"])
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--conc", type=int, default=64)
    ap.add_argument("--duration", type=float, default=10.0)
    a = ap.parse_args()

    q = mp.Queue()
    procs = [mp.Process(target=_proc,
                        args=(a.base, a.path, a.method, a.conc, a.duration, q))
             for _ in range(a.procs)]
    t0 = time.perf_counter()
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    for p in procs:
        p.join()
    elapsed = time.perf_counter() - t0

    total_ok = sum(r[0] for r in results)
    total_err = sum(r[1] for r in results)
    lat = sorted(x for r in results for x in r[2])
    p = lambda q_: lat[min(len(lat) - 1, int(q_ * len(lat)))] if lat else 0

    print(f"\n{a.method} {a.path} · {a.procs} процессов × {a.conc} воркеров "
          f"= {a.procs * a.conc} конкурентных · {elapsed:.1f}s")
    print(f"  успешных : {total_ok}   ошибок: {total_err}")
    print(f"  RPS      : {total_ok / elapsed:,.0f}")
    print(f"  p50/p90/p99 ms : {p(.5):.1f} / {p(.9):.1f} / {p(.99):.1f}")


if __name__ == "__main__":
    main()
