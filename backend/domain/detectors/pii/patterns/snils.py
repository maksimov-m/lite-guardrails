import re

from backend.domain.detectors.pii.patterns.base import PiiPattern


class SnilsPattern(PiiPattern):
    name = "snils"
    regex = r"(?<!\d)\d{3}[\s\-]\d{3}[\s\-]\d{3}[\s\-]\d{2}(?!\d)"

    def is_valid(self, value: str) -> bool:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 11:
            return False

        body, control = digits[:9], int(digits[9:])
        weighted_sum = sum(int(d) * (9 - i) for i, d in enumerate(body))

        if weighted_sum < 100:
            expected = weighted_sum
        elif weighted_sum in (100, 101):
            expected = 0
        else:
            expected = weighted_sum % 101
            if expected in (100, 101):
                expected = 0

        return expected == control
