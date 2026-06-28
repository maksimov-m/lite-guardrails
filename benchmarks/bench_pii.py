"""Бенчмарк PII-детектора на redmadrobot-rnd/pii_benchmark.

Датасет — NER в BIO-разметке (tokens + ner_tags). Наш детектор покрывает
EMAIL / PHONE / URL, поэтому считаем span-level метрики по этим типам:
эталонные спаны собираем из подряд идущих B-/I- токенов, восстанавливая
символьные офсеты, и сопоставляем с предсказаниями детектора по пересечению.

Запуск:  python benchmarks/bench_pii.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from detectors import PiiDetector

# типы датасета -> класс нашего детектора
TARGETS = {"EMAIL": "email", "PHONE": "phone", "URL": "url"}


# В датасете text — это токены, склеенные через пробелы ("ya . ru", "a @ b"),
# т.е. ненатуральный вид, ломающий регулярки. Детокенизируем в нормальный текст:
# пунктуация прилипает к словам, а @ . / - склеивают соседей (email/url/phone).
_NO_SPACE_BEFORE = set(".,;:!?%»)]}")
_NO_SPACE_AFTER = set("«([{")
_GLUE = set("@/-.")


def detokenize(tokens):
    """tokens -> (натуральный текст, [(start,end) каждого токена])."""
    out, spans = "", []
    for i, tok in enumerate(tokens):
        if i == 0:
            sep = ""
        elif tok and tok[0] in _NO_SPACE_BEFORE:
            sep = ""
        elif out and out[-1] in _NO_SPACE_AFTER:
            sep = ""
        elif (tok and tok[0] in _GLUE) or (out and out[-1] in _GLUE):
            sep = ""                       # склейка вокруг @ . / -
        else:
            sep = " "
        out += sep
        start = len(out)
        out += tok
        spans.append((start, start + len(tok)))
    return out, spans


def gold_spans(tspans, tags, target):
    """Группирует B-/I- токены типа target в символьные спаны."""
    out, i = [], 0
    while i < len(tags):
        if tags[i] == f"B-{target}":
            start = tspans[i]
            end = tspans[i]
            j = i + 1
            while j < len(tags) and tags[j] == f"I-{target}":
                if tspans[j]:
                    end = tspans[j]
                j += 1
            if start and end:
                out.append((start[0], end[1]))
            i = j
        else:
            i += 1
    return out


def overlaps(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0])


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main():
    ds = load_dataset("redmadrobot-rnd/pii_benchmark")["test"]
    det = PiiDetector()  # встроенные регулярки

    stats = {k: {"tp": 0, "fp": 0, "fn": 0} for k in TARGETS}

    for row in ds:
        tokens = json.loads(row["tokens"])
        tags = json.loads(row["ner_tags"])
        text, tspans = detokenize(tokens)

        pred = det.detect(text)["data"]
        for ds_type, cls in TARGETS.items():
            gold = gold_spans(tspans, tags, ds_type)
            preds = [(d["start"], d["end"]) for d in pred if d["class"] == cls]

            matched_pred = set()
            for g in gold:
                hit = next((i for i, p in enumerate(preds)
                            if i not in matched_pred and overlaps(g, p)), None)
                if hit is None:
                    stats[ds_type]["fn"] += 1
                else:
                    stats[ds_type]["tp"] += 1
                    matched_pred.add(hit)
            stats[ds_type]["fp"] += len(preds) - len(matched_pred)

    print(f"PII benchmark · redmadrobot-rnd/pii_benchmark · {ds.num_rows} строк\n")
    print(f"{'тип':8} {'precision':>10} {'recall':>10} {'f1':>8} "
          f"{'TP':>6} {'FP':>6} {'FN':>6}")
    print("-" * 60)
    tot = {"tp": 0, "fp": 0, "fn": 0}
    for k, s in stats.items():
        p, r, f = prf(s["tp"], s["fp"], s["fn"])
        print(f"{k:8} {p:10.3f} {r:10.3f} {f:8.3f} "
              f"{s['tp']:6} {s['fp']:6} {s['fn']:6}")
        for m in tot:
            tot[m] += s[m]
    p, r, f = prf(tot["tp"], tot["fp"], tot["fn"])
    print("-" * 60)
    print(f"{'micro':8} {p:10.3f} {r:10.3f} {f:8.3f} "
          f"{tot['tp']:6} {tot['fp']:6} {tot['fn']:6}")


if __name__ == "__main__":
    main()
