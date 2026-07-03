"""Golden-тест: Aho-Corasick NSFW-детектор даёт ИДЕНТИЧНЫЕ вердикты прежней
логике (точный матч токена по словарю). Меняется только движок матчинга.

Эталон (old_detect) повторяет прежнюю реализацию: токенизация регуляркой +
проверка вхождения токена в словарь. Сверяем и вердикт, и найденные спаны.
"""

import re

from backend.domain.detectors.nsfw import NsfwDetector

_WORD_PATTERN = re.compile(r"[0-9A-Za-zА-Яа-яЁё@$!*]+")


def old_detect(banned, text):
    text = text.lower()
    found = [
        {"value": m.group(), "start": m.start(), "end": m.end()}
        for m in _WORD_PATTERN.finditer(text)
        if m.group() in banned
    ]
    return {"NSFW_DETECT": len(found) > 0, "data": found}


BANNED = {"сука", "бля", "ass", "f@ck"}

CASES = [
    "",
    "нормальный текст без ничего",
    "ты сука",
    "СУКА большими буквами",
    "сука!",  # '!' — часть токена -> НЕ целый токен -> нет матча
    "плохо сука и ещё бля тут",  # два матча
    "class assessment",  # 'ass' внутри слов -> Scunthorpe, нет матча
    "ass",  # отдельным словом -> матч
    "напиши f@ck сюда",  # символы @ в словаре
    "сукаа",  # не тот токен -> нет матча
    "-сука-",  # дефисы — не wordchar -> матч
]


def test_ahocorasick_matches_old_token_logic_on_controlled_dict():
    det = NsfwDetector(BANNED)
    for text in CASES:
        assert det.detect(text) == old_detect(BANNED, text), f"расхождение на: {text!r}"


def test_equivalence_on_builtin_dictionary():
    words = NsfwDetector.load_builtin_words()
    det = NsfwDetector(words)
    sentences = [
        "привет как дела",
        "это отличный сервис спасибо",
        "хочу оформить заказ на завтра",
        "тут может быть ругательство из словаря",
        "смешанный текст 123 и символы !!!",
    ]
    for text in sentences:
        assert det.detect(text) == old_detect(words, text), f"расхождение на: {text!r}"


def test_empty_dictionary_never_matches():
    det = NsfwDetector(set())
    assert det.detect("любой текст сука")["NSFW_DETECT"] is False
