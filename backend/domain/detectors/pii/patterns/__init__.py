from backend.domain.detectors.pii.patterns.bank_card import BankCardPattern
from backend.domain.detectors.pii.patterns.base import PiiPattern
from backend.domain.detectors.pii.patterns.email import EmailPattern
from backend.domain.detectors.pii.patterns.inn import InnPattern
from backend.domain.detectors.pii.patterns.ip import IpPattern
from backend.domain.detectors.pii.patterns.passport import PassportRfPattern
from backend.domain.detectors.pii.patterns.phone import PhonePattern
from backend.domain.detectors.pii.patterns.snils import SnilsPattern
from backend.domain.detectors.pii.patterns.url import UrlPattern

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
