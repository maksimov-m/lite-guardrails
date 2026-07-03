from backend.domain.detectors.base import BaseDetector
from backend.domain.detectors.pii.patterns import (
    DEFAULT_PATTERNS,
    PATTERN_CLASS_BY_NAME,
    PiiPattern,
)
from backend.domain.normalization import Normalizer


class PiiDetector(BaseDetector):
    name = "pii"

    def __init__(self, patterns: dict | None = None):
        self._patterns = DEFAULT_PATTERNS if patterns is None else self._build_custom(patterns)

    @staticmethod
    def _build_custom(patterns: dict):
        built = []
        for entity, rx in patterns.items():
            pattern_class = PATTERN_CLASS_BY_NAME.get(entity, PiiPattern)
            built.append(pattern_class(name=entity, regex=rx))
        return built

    def _find_all_matches(self, text: str):
        matches = []
        for pattern in self._patterns:
            matches.extend(pattern.find(text))
        return matches

    def _keep_longest_non_overlapping(self, matches):
        matches.sort(key=lambda s: (s[0], -(s[1] - s[0])))

        accepted, last_end = [], -1
        for start, end, cls, value in matches:
            if start >= last_end:
                accepted.append((start, end, cls, value))
                last_end = end
        return accepted

    def _find_pii_spans(self, text: str):
        return self._keep_longest_non_overlapping(self._find_all_matches(text))

    def detect(self, text: str) -> dict:
        text = Normalizer.normalize(text)

        data = []
        for start, end, cls, value in self._find_pii_spans(text):
            data.append({"class": cls, "value": value, "start": start, "end": end})

        return {
            "PII_DETECT": len(data) > 0,
            "data": data,
        }

    def _assign_tags_in_order(self, spans):
        value_to_tag, counters = {}, {}
        for _, _, cls, value in spans:
            key = (cls, value)
            if key not in value_to_tag:
                counters[cls] = counters.get(cls, 0) + 1
                value_to_tag[key] = f"<{cls.upper()}_{counters[cls]}>"
        return value_to_tag

    def anonymize(self, text: str):
        spans = self._find_pii_spans(text)
        value_to_tag = self._assign_tags_in_order(spans)

        result = text
        for start, end, cls, value in sorted(spans, key=lambda s: s[0], reverse=True):
            result = result[:start] + value_to_tag[(cls, value)] + result[end:]

        mapping = {tag: value for (cls, value), tag in value_to_tag.items()}
        return result, mapping

    def deanonymize(self, text: str, mapping: dict) -> str:
        for tag, value in mapping.items():
            text = text.replace(tag, value)
        return text
