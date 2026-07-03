"""Готовит стратифицированные сэмплы из HF-датасетов redmadrobot-rnd.

PII (pii_benchmark, RU): стратификация по семействам сущностей в предложении
(contacts / documents / person / location / без сущностей) — чтобы редкие
структурные идентификаторы (СНИЛС, паспорт...) не потерялись при сэмплировании.

NSFW (nsfw_benchmark, RU+EN): стратификация по (language, type, label) —
сохраняет баланс unsafe / contrastive / hard_negative в обоих языках.

Выход: benchmarks/research/data/{pii,nsfw}_sample.jsonl (детерминированно, seed=42).
Запуск:  PYTHONPATH=. python benchmarks/research/prepare_samples.py
"""

import json
import os
import random
from collections import defaultdict

from datasets import load_dataset

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
SEED = 42
PII_TARGET = 1200
NSFW_TARGET = 1600

# BIO-тег -> семейство сущностей (сравниваем по семействам: у инструментов
# разная номенклатура типов, а семейства сопоставимы)
FAMILY_BY_TAG = {
    "FIRST_NAME": "person",
    "LAST_NAME": "person",
    "MIDDLE_NAME": "person",
    "COUNTRY": "location",
    "REGION": "location",
    "DISTRICT": "location",
    "CITY": "location",
    "STREET": "location",
    "HOUSE": "location",
    "EMAIL": "contacts",
    "PHONE": "contacts",
    "URL": "contacts",
    "IP_ADDRESS": "contacts",
    "PASSPORT": "documents",
    "INN": "documents",
    "SNILS": "documents",
    "OMS": "documents",
    "DRIVER_LICENSE": "documents",
    "BIRTH_CERTIFICATE": "documents",
    "MILITARY_ID": "documents",
    "CREDIT_CARD": "documents",
}


def tag_family(tag: str) -> str | None:
    if tag == "O":
        return None
    entity = tag.split("-", 1)[-1]  # B-EMAIL -> EMAIL
    return FAMILY_BY_TAG.get(entity, "other")


def stratified(rows, key_fn, target, rng):
    """Пропорциональный сэмпл по стратам (каждая страта представлена)."""
    by_key = defaultdict(list)
    for r in rows:
        by_key[key_fn(r)].append(r)
    total = sum(len(v) for v in by_key.values())
    picked = []
    for k in sorted(by_key, key=str):
        group = by_key[k]
        rng.shuffle(group)
        share = max(1, round(target * len(group) / total))
        picked.extend(group[:share])
    rng.shuffle(picked)
    return picked[:target]


def prepare_pii(rng):
    ds = load_dataset("redmadrobot-rnd/pii_benchmark", split="test")
    rows = []
    for r in ds:
        tokens = json.loads(r["tokens"]) if isinstance(r["tokens"], str) else r["tokens"]
        tags = json.loads(r["ner_tags"]) if isinstance(r["ner_tags"], str) else r["ner_tags"]
        fams = sorted({f for f in (tag_family(t) for t in tags) if f})
        rows.append(
            {
                "text": r["text"],
                "tokens": tokens,
                "ner_tags": tags,
                "families": fams,
            }
        )
    sample = stratified(rows, lambda r: ",".join(r["families"]) or "none", PII_TARGET, rng)
    return sample


def prepare_nsfw(rng):
    ds = load_dataset("redmadrobot-rnd/nsfw_benchmark", split="test")
    rows = [dict(r) for r in ds]
    sample = stratified(rows, lambda r: (r["language"], r["type"], r["label"]), NSFW_TARGET, rng)
    return sample


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = random.Random(SEED)

    pii = prepare_pii(rng)
    with open(os.path.join(OUT_DIR, "pii_sample.jsonl"), "w", encoding="utf-8") as f:
        for r in pii:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    fam_counts = defaultdict(int)
    for r in pii:
        for fam in r["families"] or ["none"]:
            fam_counts[fam] += 1
    print(f"PII: {len(pii)} строк; семейства: {dict(sorted(fam_counts.items()))}")

    nsfw = prepare_nsfw(rng)
    with open(os.path.join(OUT_DIR, "nsfw_sample.jsonl"), "w", encoding="utf-8") as f:
        for r in nsfw:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    strat = defaultdict(int)
    for r in nsfw:
        strat[(r["language"], r["label"])] += 1
    print(f"NSFW: {len(nsfw)} строк; (язык, label): {dict(sorted(strat.items()))}")


if __name__ == "__main__":
    main()
