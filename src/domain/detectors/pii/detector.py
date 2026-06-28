import re

from src.domain.detectors.base import BaseDetector


class PiiDetector(BaseDetector):
    """Находит персональные данные (email, url, телефон) регулярками.

    Паттерны можно передать снаружи (правила из БД) или использовать встроенные.
    """

    name = "pii"

    # Известные домены верхнего уровня для распознавания «голых» ссылок
    # (без http/www): lamoda.ru/login, stackoverflow.com/pricing и т.п.
    _TLD = (
        r"ru|рф|com|net|org|io|dev|me|info|biz|co|edu|gov|app|online|store|"
        r"site|tech|pro|su|ua|by|kz"
    )

    @classmethod
    def builtin_patterns(cls) -> dict:
        """Встроенные паттерны как {entity: исходная_строка_regex}."""
        return {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "url": (
                r"https?://[^\s]+"
                r"|www\.[^\s]+"
                # «голый» домен без схемы: каждый лейбл начинается и кончается
                # буквой/цифрой (не дефисом), матч не стартует в середине токена
                # (не после слова/@/./-), чтобы не цеплять куски доменов из email.
                rf"|(?<![\w@.\-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
                rf"(?:{cls._TLD})\b(?:/[^\s]*)?"
            ),
            "phone": (
                r"(?<!\d)(?:"
                r"(?:\+7|8)[\s\-]*\(?\s*\d{3}\s*\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"
                r"|\+\d{1,3}[\s\-]?\(?\d{3,4}\)?(?:[\s\-]?\d{2,4}){3,4}"
                r")(?!\d)"
            ),
        }

    def __init__(self, patterns: dict | None = None):
        # patterns: {entity: исходная_строка_regex}. Компилируем здесь.
        src = patterns if patterns is not None else self.builtin_patterns()
        self._patterns = {
            entity: re.compile(rx, re.IGNORECASE) for entity, rx in src.items()
        }

    def _collect_spans(self, text: str):
        """Все совпадения по всем паттернам с убранными вложениями.

        При перекрытии побеждает более длинное совпадение (email целиком, а не
        кусок его домена как url). Возвращает список (start, end, class, value),
        отсортированный по возрастанию start.
        """
        spans = []
        for pii_class, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                spans.append((m.start(), m.end(), pii_class, m.group()))
        # длинные раньше при равном начале -> при жадном проходе побеждает длинное
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))

        accepted, last_end = [], -1
        for start, end, cls, value in spans:
            if start >= last_end:           # без перекрытий
                accepted.append((start, end, cls, value))
                last_end = end
        return accepted

    def detect(self, text: str) -> dict:
        data = [
            {"class": cls, "value": value, "start": start, "end": end}
            for start, end, cls, value in self._collect_spans(text)
        ]
        return {
            "PII_DETECT": len(data) > 0,
            "data": data,
        }

    # ------------------------------------------------------------------ #
    # Анонимизация / деанонимизация
    # ------------------------------------------------------------------ #
    def anonymize(self, text: str):
        """Заменяет найденную PII на теги <CLASS_N>.

        Возвращает (анонимизированный_текст, mapping), где mapping = {тег: оригинал}.
        Одинаковое значение -> один тег; разные значения одного типа нумеруются
        1, 2, 3... в порядке появления в тексте. mapping сохраняется снаружи
        (Redis) и используется потом в deanonymize().
        """
        # Собираем все совпадения с убранными вложениями (как в detect).
        accepted = self._collect_spans(text)

        # Назначаем теги в порядке появления; дедуп по (тип, значение).
        value_to_tag, counters = {}, {}
        for start, end, cls, value in accepted:   # accepted уже по возрастанию start
            key = (cls, value)
            if key not in value_to_tag:
                counters[cls] = counters.get(cls, 0) + 1
                value_to_tag[key] = f"<{cls.upper()}_{counters[cls]}>"

        # Заменяем с конца к началу, чтобы не сдвигать индексы.
        result = text
        for start, end, cls, value in sorted(accepted, key=lambda s: s[0], reverse=True):
            result = result[:start] + value_to_tag[(cls, value)] + result[end:]

        mapping = {tag: value for (cls, value), tag in value_to_tag.items()}
        return result, mapping

    def deanonymize(self, text: str, mapping: dict) -> str:
        """Возвращает оригиналы: подставляет значения вместо тегов по mapping.

        Замена строковая (а не по позициям) — чтобы переживать переписывание
        текста между анонимизацией и деанонимизацией (например, ответом LLM).
        """
        for tag, value in mapping.items():
            text = text.replace(tag, value)
        return text
