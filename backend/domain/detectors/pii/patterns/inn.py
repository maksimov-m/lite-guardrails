import re

from backend.domain.detectors.pii.patterns.base import PiiPattern


class InnPattern(PiiPattern):
    name = "inn"
    regex = r"(?<!\d)(?:\d{12}|\d{10})(?!\d)"

    def is_valid(self, value: str) -> bool:
        digits = re.sub(r"\D", "", value)

        if len(digits) == 10:
            control = self._control_digit(digits, [2, 4, 10, 3, 5, 9, 4, 6, 8])
            return control == int(digits[9])

        if len(digits) == 12:
            first = self._control_digit(digits, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
            second = self._control_digit(digits, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
            return first == int(digits[10]) and second == int(digits[11])

        return False

    @staticmethod
    def _control_digit(digits: str, weights) -> int:
        weighted_sum = sum(int(d) * w for d, w in zip(digits, weights))
        return weighted_sum % 11 % 10
