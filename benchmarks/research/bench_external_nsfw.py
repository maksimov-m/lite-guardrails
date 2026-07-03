"""Прогон нашего NSFW-детектора на внешнем RU-бенчмарке
AlexSham/Toxic_Russian_Comments (test split, бинарная разметка toxic 0/1).

Важно: наш детектор — словарь обсценной лексики, а метка датасета — «токсичность»
(включая оскорбления/угрозы БЕЗ мата). Поэтому ждём высокую precision и невысокий
recall: словарь ловит матерную часть токсичности, но не семантическую.

Запуск: PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/bench_external_nsfw.py
"""

import json
import os
import statistics
import time

import datasets
from tqdm import tqdm

DATA = os.path.join(os.path.dirname(__file__), "data")


def make_detector():
    from backend.domain.detectors import NsfwDetector

    det = NsfwDetector(NsfwDetector.load_builtin_words())
    return lambda text: bool(det.detect(text)["NSFW_DETECT"])


def metrics(pairs):
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if not g and p)
    fn = sum(1 for g, p in pairs if g and not p)
    tn = sum(1 for g, p in pairs if not g and not p)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"accuracy": round((tp + tn) / len(pairs), 3), "precision": round(prec, 3),
            "recall": round(rec, 3), "f1": round(f1, 3),
            "n": len(pairs), "positives": tp + fn}


def main():
    ds = datasets.load_dataset("AlexSham/Toxic_Russian_Comments", split="test")
    print(f"toxic (test): {len(ds)} строк")
    run = make_detector()
    run(ds[0]["text"])  # прогрев

    pairs, lat = [], []
    for row in tqdm(ds, desc="nsfw", mininterval=2, ncols=80):
        t0 = time.perf_counter()
        p = run(row["text"])
        lat.append((time.perf_counter() - t0) * 1000)
        pairs.append((bool(row["label"]), p))

    lat.sort()
    result = {
        "dataset": "AlexSham/Toxic_Russian_Comments (test)",
        "overall": metrics(pairs),
        "latency_ms": {"avg": round(statistics.mean(lat), 4),
                       "p95": round(lat[int(len(lat) * 0.95)], 4)},
    }
    print("\n[overall]", json.dumps(result["overall"], ensure_ascii=False))
    print("латентность:", result["latency_ms"])
    with open(os.path.join(DATA, "external_nsfw_results.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("saved -> external_nsfw_results.json")


if __name__ == "__main__":
    main()
