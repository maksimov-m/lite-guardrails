from src.domain.detectors.pii.patterns.bank_card import BankCardPattern
from src.domain.detectors.pii.patterns.base import PiiPattern
from src.domain.detectors.pii.patterns.email import EmailPattern
from src.domain.detectors.pii.patterns.inn import InnPattern
from src.domain.detectors.pii.patterns.ip import IpPattern
from src.domain.detectors.pii.patterns.passport import PassportRfPattern
from src.domain.detectors.pii.patterns.phone import PhonePattern
from src.domain.detectors.pii.patterns.snils import SnilsPattern
from src.domain.detectors.pii.patterns.url import UrlPattern

DEFAULT_PATTERNS = [
    EmailPattern(),
    UrlPattern(),
    PhonePattern(),
    BankCardPattern(),
    SnilsPattern(),
    InnPattern(),
    PassportRfPattern(),
    IpPattern(),
]

PATTERN_CLASS_BY_NAME = {pattern.name: type(pattern) for pattern in DEFAULT_PATTERNS}

__all__ = [
    "PiiPattern",
    "EmailPattern",
    "UrlPattern",
    "PhonePattern",
    "BankCardPattern",
    "PassportRfPattern",
    "SnilsPattern",
    "InnPattern",
    "IpPattern",
    "DEFAULT_PATTERNS",
    "PATTERN_CLASS_BY_NAME",
]
