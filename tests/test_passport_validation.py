"""Мягкая валидация паспорта РФ (снижение FP без потери recall).

У паспорта нет контрольной суммы, поэтому PassportRfPattern.is_valid проверяет
правдоподобие серии (регион + год бланка) и отбрасывает вырожденные числа.
"""

from backend.domain.detectors import PiiDetector
from backend.domain.detectors.pii.patterns.passport import PassportRfPattern

P = PassportRfPattern()


def test_real_passports_accepted():
    # регион/год правдоподобны, слитно и с пробелами
    for v in ["4509123456", "45 09 123456", "7797000123", "92 09 000001"]:
        assert P.is_valid(v), v


def test_degenerate_numbers_rejected():
    for v in ["0000000000", "9999999999", "1234567890", "0123456789", "9876543210"]:
        assert not P.is_valid(v), v


def test_implausible_series_rejected():
    assert not P.is_valid("4534123456")  # год 34 — будущее
    assert not P.is_valid("4596123456")  # год 96 — до формата 1997
    assert not P.is_valid("9909123456")  # регион 99 — не используется
    assert not P.is_valid("0009123456")  # регион 00


def test_detector_no_passport_class_on_order_number():
    # изолируем поведение паспорта: у числового ID не должно быть класса passport_rf
    det = PiiDetector()
    r = det.detect("номер заказа 1234567890 оформлен")
    assert not any(d["class"] == "passport_rf" for d in r["data"])


def test_detector_still_flags_real_passport():
    det = PiiDetector()
    r = det.detect("паспорт 45 09 123456 выдан")
    assert r["PII_DETECT"] is True
    assert any(d["class"] == "passport_rf" for d in r["data"])
