import pytest

from src.domain.detectors.pii.detector import PiiDetector


@pytest.fixture
def detector():
    return PiiDetector()


@pytest.mark.parametrize(
    "text, expected_class, expected_value",
    [
        ("ivan@mail.ru", "email", "ivan@mail.ru"),
        ("https://example.com/path", "url", "https://example.com/path"),
        ("+7 999 123 45 67", "phone", "+7 999 123 45 67"),
        ("7707083893", "inn", "7707083893"),
        ("112-233-445 95", "snils", "112-233-445 95"),
        ("4012 8888 8888 1881", "bank_card", "4012 8888 8888 1881"),
        ("192.168.0.1", "ip", "192.168.0.1"),
        ("45 03 123456", "passport_rf", "45 03 123456"),
    ],
)
def test_detects_each_pii_type(detector, text, expected_class, expected_value):
    item = detector.detect(text)["data"][0]
    assert (item["class"], item["value"]) == (expected_class, expected_value)


def test_clean_text_reports_no_pii(detector):
    assert detector.detect("обычное предложение без данных") == {
        "PII_DETECT": False,
        "data": [],
    }


def test_offsets_point_at_detected_value(detector):
    text = "пиши на ivan@mail.ru пожалуйста"
    item = detector.detect(text)["data"][0]
    assert text.lower()[item["start"] : item["end"]] == item["value"]


def test_invalid_checksums_are_not_reported(detector):
    assert detector.detect("4012 8888 8888 1882")["data"] == []
    assert detector.detect("112-233-445 96")["data"] == []


def test_email_is_not_split_into_url(detector):
    classes = [d["class"] for d in detector.detect("ivan@mail.ru")["data"]]
    assert classes == ["email"]


def test_valid_inn_beats_passport_on_the_same_span(detector):
    assert detector.detect("7707083893")["data"][0]["class"] == "inn"
    assert detector.detect("7707083894")["data"][0]["class"] == "passport_rf"


def test_anonymize_deanonymize_is_reversible(detector):
    text = "почта ivan@mail.ru и карта 4012 8888 8888 1881"

    anonymized, mapping = detector.anonymize(text)

    assert "ivan@mail.ru" not in anonymized
    assert "<EMAIL_1>" in anonymized and "<BANK_CARD_1>" in anonymized
    assert detector.deanonymize(anonymized, mapping) == text


def test_anonymize_reuses_one_tag_for_repeated_value(detector):
    anonymized, mapping = detector.anonymize("ivan@mail.ru пишет ivan@mail.ru")
    assert anonymized.count("<EMAIL_1>") == 2
    assert len(mapping) == 1


def test_custom_db_pattern_keeps_checksum_validation():
    detector = PiiDetector(patterns={"inn": r"(?<!\d)(?:\d{12}|\d{10})(?!\d)"})
    assert detector.detect("7707083893")["data"][0]["class"] == "inn"
    assert detector.detect("7707083894")["data"] == []
