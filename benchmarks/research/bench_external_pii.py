"""Прогон нашего PII-детектора на внешнем RU-бенчмарке hivetrace/pii-bench.

Датасет: span-level разметка с char-оффсетами, 13 типов сущностей. Мы детектим
6 из них (телефон/почта/карта/ИНН/СНИЛС/паспорт) — остальные (NAME, ADDRESS,
CVC, KPP, OGRN, OGRNIP, TOKEN) вне нашего профиля.

Считаем span-level micro P/R/F1 (partial match: пересечение по символам + тот же
канонический тип) в двух срезах:
  - supported: gold только по нашим 6 типам — «на своём поле»;
  - overall:   gold по всем сущностям — реальное покрытие (recall штрафуется за
               типы, которые мы не умеем).

Запуск: PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/bench_external_pii.py
"""

import json
import os
import statistics
import time
from collections import defaultdict

import datasets
from tqdm import tqdm

DATA = os.path.join(os.path.dirname(__file__), "data")

# тип в датасете -> наш канонический класс
GOLD_TO_CANON = {
    "PHONE_NUMBER": "phone", "EMAIL": "email", "BANK_CARD_NUMBER": "bank_card",
    "INN": "inn", "SNILS": "snils", "PASSPORT_NUMBER": "passport",
}
# класс нашего детектора -> канонический (url/ip в бенчмарке не размечены — опускаем)
OURS_TO_CANON = {
    "phone": "phone", "email": "email", "bank_card": "bank_card",
    "inn": "inn", "snils": "snils", "passport_rf": "passport",
}
SUPPORTED = set(GOLD_TO_CANON.values())


def make_detector():
    from backend.domain.detectors import PiiDetector

    det = PiiDetector()

    def run(text):
        out = det.detect(text)
        return [
            (d["start"], d["end"], OURS_TO_CANON[d["class"]])
            for d in out["data"] if d["class"] in OURS_TO_CANON
        ]

    return run


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)}


def score(rows, run, supported_only):
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    lat = []
    for text, ents in rows:
        gold = [
            (e["start"], e["end"], GOLD_TO_CANON[e["type"]])
            for e in ents if e["type"] in GOLD_TO_CANON
        ] if supported_only else [
            (e["start"], e["end"], GOLD_TO_CANON.get(e["type"], e["type"]))
            for e in ents
        ]
        t0 = time.perf_counter()
        pred = run(text)
        lat.append((time.perf_counter() - t0) * 1000)

        matched = set()
        for ps, pe, pc in pred:
            hit = None
            for i, (gs, ge, gc) in enumerate(gold):
                if i not in matched and gc == pc and ps < ge and gs < pe:
                    hit = i
                    break
            if hit is None:
                fp[pc] += 1
            else:
                matched.add(hit)
                tp[pc] += 1
        for i, (_, _, gc) in enumerate(gold):
            if i not in matched:
                fn[gc] += 1

    classes = SUPPORTED if supported_only else set(tp) | set(fp) | set(fn)
    per_type = {c: {**prf(tp[c], fp[c], fn[c]), "support": tp[c] + fn[c]}
                for c in sorted(classes)}
    micro = prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))
    lat.sort()
    return {"micro": micro, "per_type": per_type,
            "latency_ms": {"avg": round(statistics.mean(lat), 3),
                           "p95": round(lat[int(len(lat) * 0.95)], 3)}}


def main():
    ds = datasets.load_dataset("hivetrace/pii-bench")
    rows = [(r["text"], r["entities"]) for split in ds.values() for r in split]
    print(f"pii-bench: {len(rows)} строк ({len(ds)} сплита)")
    run = make_detector()
    run(rows[0][0])  # прогрев

    result = {
        "dataset": "hivetrace/pii-bench",
        "rows": len(rows),
        "supported_types": score(list(tqdm(rows, desc="supported", ncols=80)), run, True),
        "overall": score(rows, run, False),
    }
    print("\n[supported — только наши 6 типов]", json.dumps(result["supported_types"]["micro"], ensure_ascii=False))
    print("[overall — все 13 типов]        ", json.dumps(result["overall"]["micro"], ensure_ascii=False))
    print("латентность:", result["supported_types"]["latency_ms"])
    with open(os.path.join(DATA, "external_pii_results.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("saved -> external_pii_results.json")


if __name__ == "__main__":
    main()
