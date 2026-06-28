import glob
import os
import re

from detectors.base import BaseDetector

_CHITCHAT_DIR = os.path.join(os.path.dirname(__file__), "data", "chitchat")


class RelevantDetector(BaseDetector):
    """Отсекает нерелевантные сообщения (смолток, мусор), чтобы не тратить на
    них токены LLM. Словарь смолтока — в data/chitchat/*.txt (файл = категория).

    Логика разбита на этапы (см. метод detect):
      Этап 0 — мусор без букв и цифр                -> блок (gibberish)
      Этап 1 — поиск фраз смолтока по словарю
      Этап 2 — доля текста, занятая смолтоком
      Этап 3 — решение: смолток доминирует -> блок
    """

    name = "relevant"

    LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
    # Блокируем, только если смолток покрывает почти ВСЁ сообщение по буквам.
    # Высокий порог (а не 0.5) убирает ложные блокировки вида «Привет, как
    # настроить роутер?» — там смолток лишь короткий префикс к реальному вопросу.
    COVERAGE_THRESHOLD = 0.8

    def __init__(self, phrases_by_category: dict | None = None):
        # phrases_by_category: {категория: [фразы]} из БД, либо None -> из файлов.
        src = phrases_by_category if phrases_by_category is not None \
            else self.load_chitchat_files()
        self._patterns = self.build_patterns(src)

    # ------------------------------------------------------------------ #
    # Загрузка словаря
    # ------------------------------------------------------------------ #
    @staticmethod
    def load_chitchat_files() -> dict:
        """Читает data/chitchat/*.txt -> {категория: [фразы]} (для сидинга)."""
        result = {}
        for path in glob.glob(os.path.join(_CHITCHAT_DIR, "*.txt")):
            category = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as f:
                phrases = [
                    line.strip() for line in f
                    if line.strip() and not line.startswith("#")
                ]
            if phrases:
                result[category] = phrases
        return result

    @staticmethod
    def build_patterns(phrases_by_category: dict) -> dict:
        """{категория: [фразы]} -> {категория: скомпилированный regex блока}."""
        compiled = {}
        for category, phrases in phrases_by_category.items():
            phrases = [p for p in phrases if p]
            if not phrases:
                continue
            # Длинные фразы раньше: в альтернации (a|b) Python берёт первое
            # подошедшее, поэтому "спасибо большое" должно стоять до "спасибо".
            phrases = sorted(phrases, key=len, reverse=True)
            # фраза -> regex (слова через \s+, границы слова по краям);
            # все паттерны блока склеиваем в ОДИН regex — один проход вместо N.
            parts = [
                rf"\b{r'\s+'.join(re.escape(w) for w in phrase.split())}\b"
                for phrase in phrases
            ]
            compiled[category] = re.compile("|".join(parts), re.IGNORECASE)
        return compiled

    # ------------------------------------------------------------------ #
    # Основной поток: этапы
    # ------------------------------------------------------------------ #
    def detect(self, text: str) -> dict:
        # Этап 0: мусор без содержания.
        if self._is_gibberish(text):
            return {"RELEVANT": False, "category": "gibberish", "data": []}

        # Этап 1: найти фразы смолтока.
        matches, scores = self._find_chitchat(text)

        # Этап 2: какую долю букв занимает смолток.
        coverage = self._coverage(text, matches)

        # Этап 3: решение.
        is_chitchat = bool(matches) and coverage >= self.COVERAGE_THRESHOLD
        top_category = max(scores, key=scores.get) if scores else None
        return {
            "RELEVANT": not is_chitchat,
            "category": top_category if is_chitchat else None,
            "data": matches,
        }

    # ------------------------------------------------------------------ #
    # Этапы (отдельными методами для читаемости)
    # ------------------------------------------------------------------ #
    def _is_gibberish(self, text: str) -> bool:
        """Этап 0: нет ни букв, ни цифр (пусто/значки/смайлики/пунктуация)."""
        has_letter = self.LETTER_RE.search(text) is not None
        has_digit = any(ch.isdigit() for ch in text)
        return not has_letter and not has_digit

    def _find_chitchat(self, text: str):
        """Этап 1: совпадения по блокам смолтока + счётчик по категориям."""
        matches = []
        scores = {}
        for category, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                matches.append({
                    "category": category,
                    "value": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                })
                scores[category] = scores.get(category, 0) + 1
        return matches, scores

    def _coverage(self, text: str, matches: list) -> float:
        """Этап 2: доля букв текста, попавших в найденный смолток."""
        covered = [False] * len(text)
        for m in matches:
            for i in range(m["start"], m["end"]):
                covered[i] = True
        total = sum(1 for ch in text if self.LETTER_RE.match(ch))
        hit = sum(
            1 for i, ch in enumerate(text)
            if covered[i] and self.LETTER_RE.match(ch)
        )
        return hit / total if total else 0
