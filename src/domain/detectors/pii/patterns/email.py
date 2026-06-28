from src.domain.detectors.pii.patterns.base import PiiPattern


class EmailPattern(PiiPattern):
    name = "email"
    regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
