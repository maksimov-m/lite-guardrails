from src.domain.detectors.pii.patterns.base import PiiPattern


class PhonePattern(PiiPattern):
    name = "phone"
    regex = (
        r"(?<!\d)(?:"
        r"(?:\+7|8)[\s\-]*\(?\s*\d{3}\s*\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"
        r"|\+\d{1,3}[\s\-]?\(?\d{3,4}\)?(?:[\s\-]?\d{2,4}){3,4}"
        r")(?!\d)"
    )
