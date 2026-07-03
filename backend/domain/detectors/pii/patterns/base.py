import regex as _regex

from backend.domain.detectors.errors import DetectorTimeout

# Потолок времени на ОДИН паттерн. Нормальный проход PII занимает <1 мс, поэтому
# 50 мс — большой запас для легитимных правил и одновременно жёсткая граница:
# катастрофический бэктрекинг в пользовательском regex превращается в быстрый
# отказ, а не в зависший воркер. Движок `regex` (надмножество `re`, поддерживает
# lookaround/бэкреференсы) умеет прерывать матчинг по таймауту — stdlib `re` нет.
MATCH_TIMEOUT_SECONDS = 0.05


class PiiPattern:
    name = ""
    regex = ""

    def __init__(self, name: str | None = None, regex: str | None = None):
        if name is not None:
            self.name = name
        if regex is not None:
            self.regex = regex
        self._compiled = _regex.compile(self.regex, _regex.IGNORECASE)

    def find(self, text: str):
        spans = []
        try:
            for match in self._compiled.finditer(text, timeout=MATCH_TIMEOUT_SECONDS):
                value = match.group()
                if self.is_valid(value):
                    spans.append((match.start(), match.end(), self.name, value))
        except TimeoutError as exc:
            # `regex` поднимает встроенный TimeoutError при превышении бюджета.
            # Fail-closed: пробрасываем наверх, API вернёт 500 (см. app.py).
            raise DetectorTimeout(self.name) from exc
        return spans

    def is_valid(self, value: str) -> bool:
        return True
