import pytest

from backend.domain.detectors.pii.patterns.bank_card import BankCardPattern
from backend.domain.detectors.pii.patterns.inn import InnPattern
from backend.domain.detectors.pii.patterns.snils import SnilsPattern


@pytest.mark.parametrize(
    "pattern_class, value",
    [
        (BankCardPattern, "4012 8888 8888 1881"),
        (InnPattern, "7707083893"),
        (InnPattern, "500100732259"),
        (SnilsPattern, "112-233-445 95"),
    ],
)
def test_checksum_accepts_valid_value(pattern_class, value):
    assert pattern_class().is_valid(value)


@pytest.mark.parametrize(
    "pattern_class, value",
    [
        (BankCardPattern, "4012 8888 8888 1882"),
        (InnPattern, "7707083894"),
        (SnilsPattern, "112-233-445 96"),
    ],
)
def test_checksum_rejects_broken_value(pattern_class, value):
    assert not pattern_class().is_valid(value)


def test_find_returns_only_checksum_valid_matches():
    pattern = BankCardPattern()
    text = "good 4012 8888 8888 1881 bad 4012 8888 8888 1882"

    spans = pattern.find(text)

    assert len(spans) == 1
    start, end, name, value = spans[0]
    assert name == "bank_card"
    assert value == "4012 8888 8888 1881"
    assert text[start:end] == value


def test_snils_matches_solid_form_without_separators():
    pattern = SnilsPattern()
    # слитный валидный СНИЛС теперь ловится (раньше regex требовал разделители)
    solid = pattern.find("снилс 11223344595 клиента")
    assert len(solid) == 1 and solid[0][3] == "11223344595"
    # разделительная форма по-прежнему работает
    assert pattern.find("112-233-445 95")
    # слитный, но с битой контрольной суммой — отсекается
    assert pattern.find("11223344596") == []
