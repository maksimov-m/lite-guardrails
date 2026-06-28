"""Асинхронное батч-логирование прогонов детекции.

Раньше каждый /detect делал синхронный INSERT+commit в Postgres прямо в
обработчике (~7 ms, сериализуется под нагрузкой). Теперь запись складывается в
in-memory очередь (микросекунды, без блокировки event loop), а фоновый воркер
дренажит её и пишет ПАЧКАМИ через bulk_insert_mappings в отдельном потоке
(asyncio.to_thread), чтобы не блокировать loop на время обращения к БД.

По одному экземпляру на каждый воркер gunicorn (своя очередь + своя задача).
"""
import asyncio
import datetime as dt
import logging

from src.adapters.db import RunLog, SessionLocal

log = logging.getLogger("runlog")

QUEUE_MAX = 20000        # потолок очереди (защита памяти при всплеске)
BATCH_MAX = 500          # макс. размер одной пачки вставки
FLUSH_INTERVAL = 0.25    # как часто просыпаться, если очередь пустует, сек


class RunLogger:
    def __init__(self):
        # Queue создаём лениво в start(): он вызывается уже внутри event loop.
        self._q: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._dropped = 0

    def start(self):
        self._q = asyncio.Queue(maxsize=QUEUE_MAX)
        self._task = asyncio.create_task(self._drain_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # дописать всё, что осталось в очереди
        if self._q is not None:
            rest = []
            while not self._q.empty():
                rest.append(self._q.get_nowait())
            if rest:
                await asyncio.to_thread(self._flush, rest)

    def log(self, module: str, input_text: str, output: str,
            duration_ms: float, meta: dict | None = None):
        """Неблокирующая постановка записи в очередь. При переполнении —
        дропаем (логирование не должно ронять/тормозить детекцию)."""
        if self._q is None:
            return
        rec = {
            "created_at": dt.datetime.utcnow(),
            "module": module,
            "input_text": input_text,
            "output": output,
            "duration_ms": duration_ms,
            "meta": meta or None,
        }
        try:
            self._q.put_nowait(rec)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped % 1000 == 1:
                log.warning("runlog: очередь переполнена, потеряно ~%d записей",
                            self._dropped)

    async def _drain_loop(self):
        while True:
            # ждём первую запись (с таймаутом, чтобы реагировать на отмену)
            try:
                first = await asyncio.wait_for(self._q.get(), FLUSH_INTERVAL)
            except asyncio.TimeoutError:
                continue
            batch = [first]
            # добираем всё, что уже накопилось, до BATCH_MAX
            while len(batch) < BATCH_MAX:
                try:
                    batch.append(self._q.get_nowait())
                except asyncio.QueueEmpty:
                    break
            await asyncio.to_thread(self._flush, batch)

    @staticmethod
    def _flush(batch: list[dict]):
        try:
            with SessionLocal() as s:
                s.bulk_insert_mappings(RunLog, batch)
                s.commit()
        except Exception as e:        # БД могла моргнуть — не роняем воркер
            log.warning("runlog: не удалось записать пачку из %d (%s)",
                        len(batch), e)
