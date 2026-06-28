"""Бенчмарк NSFW-детектора на redmadrobot-rnd/nsfw_benchmark.

Датасет — бинарная разметка (label: 1 = nsfw, 0 = безопасно), ru+en.
Наш детектор словарный (NSFW_DETECT bool), поэтому считаем precision/recall/
F1/accuracy и разбивку по языку. Низкий recall — ожидаемое ограничение
словарного подхода (см. вывод), это не классификатор безопасности.

Запуск:  python benchmarks/bench_nsfw.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from detectors import NsfwDetector


def prf(tp, fp, fn, tn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    acc = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) else 0.0
    return p, r, f, acc


def main():
    ds = load_dataset("redmadrobot-rnd/nsfw_benchmark")["test"]
    det = NsfwDetector()  # встроенный словарь RU+EN

    # счётчики: общий и по языку
    cells = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})

    for row in ds:
        gold = int(row["label"]) == 1
        pred = det.detect(row["text"])["NSFW_DETECT"]
        cell = ("tp" if gold and pred else "fn" if gold else
                "fp" if pred else "tn")
        cells["all"][cell] += 1
        cells[row.get("language") or "?"][cell] += 1

    print(f"NSFW benchmark · redmadrobot-rnd/nsfw_benchmark · {ds.num_rows} строк")
    print("(label 1 = nsfw, 0 = безопасно)\n")
    print(f"{'срез':8} {'precision':>10} {'recall':>10} {'f1':>8} "
          f"{'accuracy':>9} {'TP':>6} {'FP':>6} {'FN':>6} {'TN':>6}")
    print("-" * 78)
    for key in ["all", "ru", "en"]:
        if key not in cells:
            continue
        s = cells[key]
        p, r, f, acc = prf(s["tp"], s["fp"], s["fn"], s["tn"])
        print(f"{key:8} {p:10.3f} {r:10.3f} {f:8.3f} {acc:9.3f} "
              f"{s['tp']:6} {s['fp']:6} {s['fn']:6} {s['tn']:6}")
    print("\nПримечание: словарь ловит явную лексику (высокая precision), но не "
          "распознаёт\nперефразированный/неявный nsfw -> низкий recall. Это "
          "ожидаемо для\nсловарного подхода без ML.")


if __name__ == "__main__":
    main()
