import os

from better_profanity import Profanity


def normalize_words(words) -> set:
    return {w.strip().lower() for w in (words or []) if w.strip()}


def read_txt_dictionaries(data_dir: str) -> set:
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"NSFW: папка словарей не найдена: {data_dir}")

    txt_files = sorted(name for name in os.listdir(data_dir) if name.lower().endswith(".txt"))
    if not txt_files:
        raise FileNotFoundError(f"NSFW: в {data_dir} нет ни одного .txt-словаря")

    words = set()
    for name in txt_files:
        with open(os.path.join(data_dir, name), encoding="utf-8") as f:
            words |= normalize_words(f)

    if not words:
        raise ValueError(f"NSFW: .txt-словари в {data_dir} пустые")
    return words


def load_english_profanity() -> set:
    engine = Profanity()
    engine.load_censor_words()
    return {str(word).lower() for word in engine.CENSOR_WORDSET}


def build_builtin_words(data_dir: str) -> set:
    return read_txt_dictionaries(data_dir) | load_english_profanity()
