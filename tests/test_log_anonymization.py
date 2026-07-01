from src.domain.detectors import PiiDetector
from src.entrypoints.detectors.log_utils import anonymize_from_spans, build_log_payload

PHONE = "+79161234567"


def test_anonymize_from_spans_replaces_pii():
    det = PiiDetector()
    text = f"мой телефон {PHONE}"
    result = det.detect(text)
    out = anonymize_from_spans(text, result["data"])
    assert PHONE not in out
    assert "<PHONE_1>" in out


def test_anonymize_from_spans_dedupes_same_value():
    det = PiiDetector()
    text = f"{PHONE} и снова {PHONE}"
    out = anonymize_from_spans(text, det.detect(text)["data"])
    assert out.count("<PHONE_1>") == 2  # одинаковое значение -> один тег
    assert "<PHONE_2>" not in out


def test_pii_module_logs_anonymized_and_masks_output():
    det = PiiDetector()
    text = f"телефон {PHONE}"
    result = det.detect(text)
    log_text, log_output = build_log_payload("pii", text, result)
    assert PHONE not in log_text and "<PHONE_1>" in log_text
    assert all(d["value"] is None for d in log_output["data"])
    # исходный result не мутировали — ответ клиенту полный
    assert any(d["value"] == PHONE for d in result["data"])


def test_non_pii_module_logs_raw():
    text = f"позвони на {PHONE}"
    result = {"NSFW_DETECT": False, "data": []}
    log_text, log_output = build_log_payload("nsfw", text, result)
    assert log_text == text          # для не-pii модулей текст не трогаем
    assert log_output == result


def test_log_raw_input_toggle(monkeypatch):
    from src.entrypoints.detectors import log_utils

    monkeypatch.setattr(log_utils.settings, "log_raw_input", True)
    det = PiiDetector()
    text = f"телефон {PHONE}"
    result = det.detect(text)
    log_text, log_output = build_log_payload("pii", text, result)
    assert log_text == text          # raw-режим: не анонимизируем даже pii
    assert log_output == result
