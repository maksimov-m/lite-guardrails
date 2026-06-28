import pytest

from src.domain.detectors.pii.patterns.bank_card import BankCardPattern
from src.domain.detectors.pii.patterns.inn import InnPattern
from src.domain.detectors.pii.patterns.snils import SnilsPattern


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
