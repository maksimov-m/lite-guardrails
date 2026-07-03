"""Собирает самодостаточный HTML-отчёт из pii_results.json и nsfw_results.json.

Запуск:  PYTHONPATH=. python benchmarks/research/make_report.py
Выход:   benchmarks/research/report.html
"""

import datetime as dt
import json
import os

DATA = os.path.join(os.path.dirname(__file__), "data")
OUT = os.path.join(os.path.dirname(__file__), "report.html")

SYS_LABEL = {
    "lite-guardrails": "lite-guardrails (наш)",
    "presidio": "Microsoft Presidio",
    "llm-guard": "LLM Guard (Protect AI)",
}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def bar(value, vmax=1.0, kind="ok"):
    pct = round(100 * value / vmax) if vmax else 0
    return (
        f'<div class="bar"><div class="fill {kind}" style="width:{pct}%"></div>'
        f"<span>{value:.3f}</span></div>"
    )


def best(values):
    """индекс максимума (для подсветки лучшего)."""
    return max(range(len(values)), key=lambda i: values[i]) if values else -1


def pii_section(pii):
    systems = list(pii["systems"])
    rows = ""
    # микро P/R/F1 + латентность
    metrics = [("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
    head = "".join(f"<th>{SYS_LABEL[s]}</th>" for s in systems)
    for key, title in metrics:
        vals = [pii["systems"][s]["micro"][key] for s in systems]
        bi = best(vals)
        cells = "".join(
            f'<td class="{"win" if i == bi else ""}">{bar(v, 1.0)}</td>' for i, v in enumerate(vals)
        )
        rows += f"<tr><th>{title} (micro)</th>{cells}</tr>"
    # латентность (меньше = лучше)
    lat = [pii["systems"][s]["latency_ms"]["avg"] for s in systems]
    bi = min(range(len(lat)), key=lambda i: lat[i])
    cells = "".join(
        f'<td class="{"win" if i == bi else ""}">{v:.2f} мс</td>' for i, v in enumerate(lat)
    )
    rows += f"<tr><th>Латентность (avg)</th>{cells}</tr>"
    p95 = [pii["systems"][s]["latency_ms"]["p95"] for s in systems]
    cells = "".join(f"<td>{v:.2f} мс</td>" for v in p95)
    rows += f"<tr><th>Латентность (p95)</th>{cells}</tr>"

    # по семействам — F1
    fams = ["contacts", "documents", "person", "location"]
    fam_rows = ""
    for fam in fams:
        vals = [pii["systems"][s]["families"][fam]["f1"] for s in systems]
        sup = pii["systems"][systems[0]]["families"][fam]["support"]
        bi = best(vals)
        cells = "".join(
            f'<td class="{"win" if i == bi else ""}">{bar(v, 1.0)}</td>' for i, v in enumerate(vals)
        )
        fam_rows += f"<tr><th>{fam} <span class=mut>· n={sup}</span></th>{cells}</tr>"

    return f"""
    <h2>PII-детекция</h2>
    <p class="mut">Датасет <code>redmadrobot-rnd/pii_benchmark</code> (RU), сэмпл {pii["sample_size"]} строк.
    Метрика — span-level micro P/R/F1 с partial-match по семействам сущностей.</p>
    <table><thead><tr><th>Метрика</th>{head}</tr></thead><tbody>{rows}</tbody></table>
    <h3>F1 по семействам сущностей</h3>
    <table><thead><tr><th>Семейство</th>{head}</tr></thead><tbody>{fam_rows}</tbody></table>
    """


def nsfw_section(nsfw):
    systems = list(nsfw["systems"])
    head = "".join(f"<th>{SYS_LABEL[s]}</th>" for s in systems)
    rows = ""
    for key, title in [
        ("accuracy", "Accuracy"),
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1", "F1"),
    ]:
        vals = [nsfw["systems"][s]["overall"][key] for s in systems]
        bi = best(vals)
        cells = "".join(
            f'<td class="{"win" if i == bi else ""}">{bar(v, 1.0)}</td>' for i, v in enumerate(vals)
        )
        rows += f"<tr><th>{title}</th>{cells}</tr>"
    lat = [nsfw["systems"][s]["latency_ms"]["avg"] for s in systems]
    bi = min(range(len(lat)), key=lambda i: lat[i])
    cells = "".join(
        f'<td class="{"win" if i == bi else ""}">{v:.2f} мс</td>' for i, v in enumerate(lat)
    )
    rows += f"<tr><th>Латентность (avg)</th>{cells}</tr>"

    # F1 по языкам
    lang_rows = ""
    langs = list(nsfw["systems"][systems[0]]["by_language"])
    for lang in langs:
        vals = [nsfw["systems"][s]["by_language"][lang]["f1"] for s in systems]
        bi = best(vals)
        cells = "".join(
            f'<td class="{"win" if i == bi else ""}">{bar(v, 1.0)}</td>' for i, v in enumerate(vals)
        )
        lang_rows += f"<tr><th>{lang.upper()}</th>{cells}</tr>"

    return f"""
    <h2>NSFW / toxicity-детекция</h2>
    <p class="mut">Датасет <code>redmadrobot-rnd/nsfw_benchmark</code> (RU+EN), сэмпл {nsfw["sample_size"]} строк.
    Бинарная классификация (unsafe = 1). lite использует словарь, LLM Guard — ML-модель (roberta).</p>
    <table><thead><tr><th>Метрика</th>{head}</tr></thead><tbody>{rows}</tbody></table>
    <h3>F1 по языкам</h3>
    <table><thead><tr><th>Язык</th>{head}</tr></thead><tbody>{lang_rows}</tbody></table>
    """


def conclusions(pii, nsfw):
    S = pii["systems"]
    lite_f1 = S["lite-guardrails"]["micro"]["f1"]
    lite_p = S["lite-guardrails"]["micro"]["precision"]
    lite_doc = S["lite-guardrails"]["families"]["documents"]["f1"]
    pre_f1 = S["presidio"]["micro"]["f1"]
    pre_per = S["presidio"]["families"]["person"]["f1"]
    lite_lat = S["lite-guardrails"]["latency_ms"]["avg"]
    pre_lat = S["presidio"]["latency_ms"]["avg"]
    lg_lat = S["llm-guard"]["latency_ms"]["avg"]
    speed = round(pre_lat / lite_lat) if lite_lat else 0
    lg_speed = round(lg_lat / lite_lat) if lite_lat else 0

    N = nsfw["systems"]
    lite_nsfw = N["lite-guardrails"]["overall"]
    lg_nsfw = N["llm-guard"]["overall"]
    lite_nsfw_lat = N["lite-guardrails"]["latency_ms"]["avg"]
    lg_nsfw_lat = N["llm-guard"]["latency_ms"]["avg"]
    nsfw_speed = round(lg_nsfw_lat / lite_nsfw_lat) if lite_nsfw_lat else 0
    # сравнение по факту (не предполагаем, кто лучше)
    lite_wins_nsfw = lite_nsfw["f1"] >= lg_nsfw["f1"]
    nsfw_verdict = (
        f"На этом датасете словарь даже слегка обошёл ML-модель по F1 "
        f"(<b>{lite_nsfw['f1']:.2f}</b> против <b>{lg_nsfw['f1']:.2f}</b>) — обе системы "
        f"«проседают» по recall (0.10 и 0.08): семантические категории (экстремизм, "
        f"политика, self-harm) и hard-negative-примеры плохо ловятся и списком слов, и "
        f"англоязычной toxicity-моделью на русском тексте."
        if lite_wins_nsfw
        else f"ML-модель полнее по recall (<b>{lg_nsfw['recall']:.2f}</b> против "
        f"<b>{lite_nsfw['recall']:.2f}</b>), но ценой латентности."
    )

    return f"""
    <h2>Выводы</h2>
    <div class="cards">
      <div class="card">
        <h4>Скорость</h4>
        <p>lite-guardrails — <b>~{lite_lat:.2f} мс</b> на PII-запрос против <b>{pre_lat:.0f} мс</b> у Presidio
        (≈ {speed}×) и <b>{lg_lat:.0f} мс</b> у LLM Guard (≈ <b>{lg_speed:,}×</b>). На NSFW —
        <b>{lite_nsfw_lat:.2f} мс</b> против {lg_nsfw_lat:.0f} мс (≈ <b>{nsfw_speed:,}×</b>).
        Причина — regex/словарь на CPU против ML-моделей (spaCy / BERT-large / roberta).</p>
      </div>
      <div class="card">
        <h4>PII: точность vs полнота</h4>
        <p>Наш детектор бьёт по структурным идентификаторам: precision <b>{lite_p:.2f}</b>,
        documents-F1 <b>{lite_doc:.2f}</b> — почти без ложных срабатываний на картах/СНИЛС/ИНН/телефонах.
        Но общий F1 <b>{lite_f1:.2f}</b> низкий, потому что имена и адреса он не детектит вовсе —
        их закрывает NER Presidio (person-F1 <b>{pre_per:.2f}</b>, общий <b>{pre_f1:.2f}</b>).</p>
      </div>
      <div class="card">
        <h4>NSFW: словарь vs модель</h4>
        <p>Словарь даёт высокую precision (<b>{lite_nsfw["precision"]:.2f}</b>) при низком recall
        (<b>{lite_nsfw["recall"]:.2f}</b>). {nsfw_verdict}</p>
      </div>
      <div class="card">
        <h4>Ниша lite-guardrails</h4>
        <p>Не «умнее» тяжёлых решений, а <b>быстрый и предсказуемый первый слой</b>: structured-PII с
        анонимизацией и фильтр профанити на 4–5 порядков дешевле по латентности, self-hosted, RU-first.
        Для имён/адресов и семантической токсичности нужен ML-слой (NER + toxicity-модель) — это следующий шаг развития.</p>
      </div>
    </div>
    """


def main():
    pii = load("pii_results.json")
    nsfw = load("nsfw_results.json")
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>lite-guardrails · бенчмарк</title>
<style>
  :root {{ --fg:#1a1a2e; --mut:#6b7280; --line:#e5e7eb; --ok:#4f8cff; --win:#e8f0ff; }}
  * {{ box-sizing:border-box; }}
  body {{ font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif; color:var(--fg);
         max-width:960px; margin:0 auto; padding:32px 20px; }}
  h1 {{ margin:0 0 4px; }} h2 {{ margin-top:40px; border-bottom:2px solid var(--line); padding-bottom:6px; }}
  h3 {{ margin-top:24px; color:#334; }} .mut {{ color:var(--mut); }}
  code {{ background:#f3f4f6; padding:1px 5px; border-radius:4px; font-size:13px; }}
  table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:14px; }}
  th,td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; }}
  thead th {{ background:#f9fafb; }} td.win {{ background:var(--win); }}
  tbody th {{ font-weight:600; background:#fcfcfd; white-space:nowrap; }}
  .bar {{ position:relative; background:#f3f4f6; border-radius:4px; height:22px; min-width:120px; }}
  .bar .fill {{ position:absolute; inset:0 auto 0 0; background:var(--ok); border-radius:4px; opacity:.85; }}
  .bar span {{ position:relative; padding-left:8px; font-variant-numeric:tabular-nums;
              line-height:22px; font-size:13px; }}
  .cards {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  .card {{ border:1px solid var(--line); border-radius:10px; padding:14px 16px; background:#fbfcfe; }}
  .card h4 {{ margin:0 0 6px; }} .card p {{ margin:0; font-size:14px; }}
  .note {{ background:#fff8e6; border:1px solid #f0e0b0; border-radius:8px; padding:12px 16px; font-size:13px; }}
  @media (max-width:640px) {{ .cards {{ grid-template-columns:1fr; }} }}
</style></head><body>
<h1>🛡️ lite-guardrails — сравнительный бенчмарк</h1>
<p class="mut">Сгенерировано {now}. Синие полосы — метрика от 0 до 1 (больше = лучше);
голубым выделен лучший в строке.</p>

<div class="note">
<b>Методология.</b> Стратифицированные сэмплы (seed=42): PII — по семействам сущностей,
NSFW — по (язык, тип, метка). PII-метрика — span-level micro-F1 с partial-match (пересечение
по символам, один gold ↔ одно предсказание). NSFW — бинарная классификация unsafe.
Латентность — среднее время на один текст на CPU (без GPU). Числа зависят от железа и
сэмпла; воспроизводимо скриптами в <code>benchmarks/research/</code>.
</div>

{pii_section(pii)}
{nsfw_section(nsfw)}
{conclusions(pii, nsfw)}

<h2 class="mut" style="font-size:15px;border:0">Участники</h2>
<p class="mut">lite-guardrails (regex+checksum PII, словарь NSFW) ·
Microsoft Presidio (spaCy-ru NER + pattern recognizers) ·
LLM Guard / Protect AI (BERT-NER для PII, unbiased-toxic-roberta для toxicity).</p>
</body></html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
