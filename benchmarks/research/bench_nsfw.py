"""NSFW-бенчмарк: lite-guardrails (словарь) vs LLM Guard Toxicity (ML).

Датасет: redmadrobot-rnd/nsfw_benchmark (RU+EN), стратифицированный сэмпл.
Бинарная классификация: label 1 = unsafe. Метрики: accuracy/P/R/F1 —
общие, по языкам и по типам примеров (unsafe / contrastive / hard_negative).
Скорость: время классификации одного текста.

Запуск:  PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/bench_nsfw.py
Выход:   benchmarks/research/data/nsfw_results.json
"""

import json
import os
import statistics
import time
from collections import defaultdict

from tqdm import tqdm

DATA = os.path.join(os.path.dirname(__file__), "data")


def load_sample():
    with open(os.path.join(DATA, "nsfw_sample.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def make_lite():
    from backend.domain.detectors import NsfwDetector

    det = NsfwDetector(NsfwDetector.load_builtin_words())
    return lambda text: bool(det.detect(text)["NSFW_DETECT"])


def make_llm_guard():
    from llm_guard.input_scanners import Toxicity

    scanner = Toxicity()  # unbiased-toxic-roberta, порог по умолчанию

    def run(text):
        _, is_valid, _ = scanner.scan(text)
        return not is_valid  # invalid = токсично

    return run


def metrics(pairs):
    """pairs: [(gold, pred)] -> accuracy/precision/recall/f1."""
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if not g and p)
    fn = sum(1 for g, p in pairs if g and not p)
    tn = sum(1 for g, p in pairs if not g and not p)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "accuracy": round((tp + tn) / len(pairs), 3) if pairs else 0.0,
        "precision": round(prec, 3),
        "recall": round(rec, 3),
        "f1": round(f1, 3),
        "n": len(pairs),
    }


def evaluate(run, rows, desc="eval"):
    preds, lat = [], []
    for r in tqdm(rows, desc=desc, mininterval=2, ncols=80):
        t0 = time.perf_counter()
        p = run(r["text"])
        lat.append((time.perf_counter() - t0) * 1000)
        preds.append(p)

    pairs_all = [(bool(r["label"]), p) for r, p in zip(rows, preds)]
    by_lang = defaultdict(list)
    by_type = defaultdict(list)
    for r, pair in zip(rows, pairs_all):
        by_lang[r["language"] or "?"].append(pair)
        by_type[r["type"] or "unsafe"].append(pair)  # None -> unsafe (позитивы)

    lat.sort()
    return {
        "overall": metrics(pairs_all),
        "by_language": {
            k: metrics(v) for k, v in sorted(by_lang.items(), key=lambda kv: str(kv[0]))
        },
        "by_type": {k: metrics(v) for k, v in sorted(by_type.items(), key=lambda kv: str(kv[0]))},
        "latency_ms": {
            "avg": round(statistics.mean(lat), 2),
            "p50": round(lat[len(lat) // 2], 2),
            "p95": round(lat[int(len(lat) * 0.95)], 2),
        },
    }


def main():
    rows = load_sample()
    print(f"NSFW sample: {len(rows)} строк")
    systems = {"lite-guardrails": make_lite, "llm-guard": make_llm_guard}
    results = {}
    for name, factory in systems.items():
        print(f"--- {name}: инициализация...")
        run = factory()
        run(rows[0]["text"])  # прогрев
        results[name] = evaluate(run, rows, desc=f"NSFW/{name}")
        print(json.dumps(results[name]["overall"], ensure_ascii=False), results[name]["latency_ms"])
    with open(os.path.join(DATA, "nsfw_results.json"), "w", encoding="utf-8") as f:
        json.dump({"sample_size": len(rows), "systems": results}, f, ensure_ascii=False, indent=2)
    print("saved -> nsfw_results.json")


if __name__ == "__main__":
    main()
