from src.domain.detectors.pii.patterns.base import PiiPattern

_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"


class IpPattern(PiiPattern):

    name = "ip"
    regex = rf"(?<![\w.])(?:{_OCTET}\.){{3}}{_OCTET}(?![\w.])"
