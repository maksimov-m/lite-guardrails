import glob
import os
import re


def read_chitchat_files(data_dir: str) -> dict:
    categories = {}
    # sorted(): порядок glob зависит от ФС и различается между ОС — фиксируем его,
    # чтобы порядок категорий (а значит и tie-break top-категории) был детерминирован.
    for path in sorted(glob.glob(os.path.join(data_dir, "*.txt"))):
        category = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            phrases = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if phrases:
            categories[category] = phrases
    return categories


def build_category_patterns(phrases_by_category: dict) -> dict:
    patterns = {}
    for category, phrases in phrases_by_category.items():
        phrases = sorted((p for p in phrases if p), key=len, reverse=True)
        if not phrases:
            continue
        alternatives = [
            rf"\b{r'\s+'.join(re.escape(word) for word in phrase.split())}\b" for phrase in phrases
        ]
        patterns[category] = re.compile("|".join(alternatives), re.IGNORECASE)
    return patterns
