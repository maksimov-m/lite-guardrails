import re

from src.domain.detectors.pii.patterns.base import PiiPattern


class BankCardPattern(PiiPattern):
    name = "bank_card"
    regex = r"(?<!\d)(?:\d{4}[\s\-]?){3}\d{4}(?!\d)"

    def is_valid(self, value: str) -> bool:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 12:
            return False

        total = 0
        for index, char in enumerate(reversed(digits)):
            digit = int(char)
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0
