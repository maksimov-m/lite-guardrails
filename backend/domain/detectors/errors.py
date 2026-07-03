class DetectorTimeout(Exception):
    """Матчинг детектора не уложился в бюджет времени — вероятен катастрофический
    бэктрекинг в пользовательском regex-правиле.

    Обрабатывается на уровне API как отказ (fail-closed): для PII-гуарда лучше
    вернуть ошибку, чем молча пропустить непросканированный текст. Заодно это
    превращает ReDoS-атаку в быстрый отказ (~бюджет), а не в зависший воркер.
    """

    def __init__(self, pattern_name: str):
        self.pattern_name = pattern_name
        super().__init__(f"detector pattern '{pattern_name}' exceeded time budget")
