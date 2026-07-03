"""PII-бенчмарк: lite-guardrails vs Microsoft Presidio vs LLM Guard (Anonymize).

Датасет: redmadrobot-rnd/pii_benchmark (RU), стратифицированный сэмпл.
Сущности сгруппированы в семейства (contacts/documents/person/location) —
номенклатура типов у инструментов разная, семейства сопоставимы.

Метрика: span-level precision/recall/F1 с partial match (предсказанный спан
засчитывается, если пересекается по символам с gold-спаном того же семейства;
каждый gold матчится максимум один раз). Скорость: время анализа одного текста.

Запуск:  PYTHONPATH=. PYTHONIOENCODING=utf-8 python benchmarks/research/bench_pii.py
Выход:   benchmarks/research/data/pii_results.json
"""

import json
import os
import statistics
import time
from collections import defaultdict

from tqdm import tqdm

DATA = os.path.join(os.path.dirname(__file__), "data")

FAMILY_BY_TAG = {
    "FIRST_NAME": "person", "LAST_NAME": "person", "MIDDLE_NAME": "person",
    "COUNTRY": "location", "REGION": "location", "DISTRICT": "location",
    "CITY": "location", "STREET": "location", "HOUSE": "location",
    "EMAIL": "contacts", "PHONE": "contacts", "URL": "contacts",
    "IP_ADDRESS": "contacts",
    "PASSPORT": "documents", "INN": "documents", "SNILS": "documents",
    "OMS": "documents", "DRIVER_LICENSE": "documents",
    "BIRTH_CERTIFICATE": "documents", "MILITARY_ID": "documents",
    "CREDIT_CARD": "documents",
}
FAMILIES = ("contacts", "documents", "person", "location")


def load_sample():
    rows = []
    with open(os.path.join(DATA, "pii_sample.jsonl"), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def gold_spans(row):
    """BIO-теги -> char-спаны (start, end, family). Токены ищем в тексте слева
    направо — так восстанавливаются исходные оффсеты."""
    text, cursor, spans = row["text"], 0, []
    positions = []
    for tok in row["tokens"]:
        idx = text.find(tok, cursor)
        if idx < 0:  # токенизация разошлась с текстом — пропускаем токен
            positions.append(None)
            continue
        positions.append((idx, idx + len(tok)))
        cursor = idx + len(tok)

    current = None  # (start, end, family)
    for pos, tag in zip(positions, row["ner_tags"]):
        fam = FAMILY_BY_TAG.get(tag.split("-", 1)[-1]) if tag != "O" else None
        starts_new = tag.startswith("B-") or (fam and not current)
        if pos is None or fam is None:
            if current:
                spans.append(current)
                current = None
            continue
        if starts_new or (current and current[2] != fam):
            if current:
                spans.append(current)
            current = (pos[0], pos[1], fam)
        else:
            current = (current[0], pos[1], current[2])
    if current:
        spans.append(current)
    return spans


# --------------------------------------------------------------------------- #
# Системы: каждая возвращает список (start, end, family)
# --------------------------------------------------------------------------- #
def make_lite():
    from backend.domain.detectors import PiiDetector

    det = PiiDetector()
    fam = {
        "email": "contacts", "phone": "contacts", "url": "contacts", "ip": "contacts",
        "bank_card": "documents", "snils": "documents", "inn": "documents",
        "passport": "documents",
    }

    def run(text):
        out = det.detect(text)
        return [
            (d["start"], d["end"], fam[d["class"]])
            for d in out["data"] if d["class"] in fam
        ]

    return run


def make_presidio():
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "ru", "model_name": "ru_core_news_md"}],
    })
    nlp = provider.create_engine()
    # Дефолтный registry сам соберёт рекогнайзеры под ru: pattern-based (email,
    # phone, credit card, IP, URL — язык-агностичны) + PERSON/LOC из spaCy-ru.
    analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["ru"])
    fam = {
        "EMAIL_ADDRESS": "contacts", "PHONE_NUMBER": "contacts",
        "URL": "contacts", "IP_ADDRESS": "contacts",
        "CREDIT_CARD": "documents",
        "PERSON": "person", "PER": "person",
        "LOCATION": "location", "LOC": "location", "GPE": "location",
    }

    def run(text):
        return [
            (r.start, r.end, fam[r.entity_type])
            for r in analyzer.analyze(text=text, language="ru")
            if r.entity_type in fam
        ]

    return run


def make_llm_guard():
    from llm_guard.input_scanners import Anonymize
    from llm_guard.input_scanners.anonymize_helpers import BERT_LARGE_NER_CONF
    from llm_guard.vault import Vault

    scanner = Anonymize(Vault(), recognizer_conf=BERT_LARGE_NER_CONF,
                        language="en")  # RU не поддерживается — честно фиксируем
    fam = {
        "EMAIL_ADDRESS": "contacts", "EMAIL_ADDRESS_RE": "contacts",
        "PHONE_NUMBER": "contacts", "PHONE_NUMBER_WITH_EXT": "contacts",
        "URL": "contacts", "URL_RE": "contacts", "IP_ADDRESS": "contacts",
        "CREDIT_CARD": "documents", "CREDIT_CARD_RE": "documents",
        "US_SSN": "documents", "US_SSN_RE": "documents",
        "PERSON": "person", "LOCATION": "location",
    }
    analyzer = scanner._analyzer  # используем анализатор напрямую: нужны спаны

    def run(text):
        return [
            (r.start, r.end, fam[r.entity_type])
            for r in analyzer.analyze(text=text, language="en")
            if r.entity_type in fam
        ]

    return run


# --------------------------------------------------------------------------- #
def evaluate(run, rows, desc="eval"):
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    lat = []
    for row in tqdm(rows, desc=desc, mininterval=2, ncols=80):
        gold = gold_spans(row)
        t0 = time.perf_counter()
        pred = run(row["text"])
        lat.append((time.perf_counter() - t0) * 1000)

        matched = set()
        for ps, pe, pf in pred:
            hit = None
            for i, (gs, ge, gf) in enumerate(gold):
                if i not in matched and gf == pf and ps < ge and gs < pe:
                    hit = i
                    break
            if hit is None:
                fp[pf] += 1
            else:
                matched.add(hit)
                tp[pf] += 1
        for i, (_, _, gf) in enumerate(gold):
            if i not in matched:
                fn[gf] += 1

    def prf(t, f_p, f_n):
        p = t / (t + f_p) if t + f_p else 0.0
        r = t / (t + f_n) if t + f_n else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)}

    families = {
        fam: {**prf(tp[fam], fp[fam], fn[fam]),
              "support": tp[fam] + fn[fam]}
        for fam in FAMILIES
    }
    total = prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))
    lat.sort()
    return {
        "families": families,
        "micro": total,
        "latency_ms": {
            "avg": round(statistics.mean(lat), 2),
            "p50": round(lat[len(lat) // 2], 2),
            "p95": round(lat[int(len(lat) * 0.95)], 2),
        },
    }


def main():
    rows = load_sample()
    print(f"PII sample: {len(rows)} строк")
    systems = {
        "lite-guardrails": make_lite,
        "presidio": make_presidio,
        "llm-guard": make_llm_guard,
    }
    results = {}
    for name, factory in systems.items():
        print(f"--- {name}: инициализация...")
        run = factory()
        run(rows[0]["text"])  # прогрев (кэши/модель)
        results[name] = evaluate(run, rows, desc=f"PII/{name}")
        print(json.dumps(results[name]["micro"], ensure_ascii=False),
              results[name]["latency_ms"])
    with open(os.path.join(DATA, "pii_results.json"), "w", encoding="utf-8") as f:
        json.dump({"sample_size": len(rows), "systems": results}, f,
                  ensure_ascii=False, indent=2)
    print("saved -> pii_results.json")


if __name__ == "__main__":
    main()
