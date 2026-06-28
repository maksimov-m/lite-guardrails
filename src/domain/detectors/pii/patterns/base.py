import re


class PiiPattern:

    name = ""
    regex = ""

    def __init__(self, name: str | None = None, regex: str | None = None):
        if name is not None:
            self.name = name
        if regex is not None:
            self.regex = regex
        self._compiled = re.compile(self.regex, re.IGNORECASE)

    def find(self, text: str):
        spans = []
        for match in self._compiled.finditer(text):
            value = match.group()
            if self.is_valid(value):
                spans.append((match.start(), match.end(), self.name, value))
        return spans

    def is_valid(self, value: str) -> bool:
        return True
