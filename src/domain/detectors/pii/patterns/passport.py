from src.domain.detectors.pii.patterns.base import PiiPattern


class PassportRfPattern(PiiPattern):
    name = "passport_rf"
    regex = r"(?<!\d)\d{2}\s?\d{2}\s?\d{6}(?!\d)"
