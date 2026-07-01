from types import SimpleNamespace

from src.engine import GuardEngine


def test_build_pii_groups_by_type_and_skips_disabled():
    detector = GuardEngine._build_pii([
        SimpleNamespace(type="EMAIL", regex=r"[a-z0-9.]+@[a-z]+\.[a-z]+", enabled=True),
        SimpleNamespace(type="PHONE", regex=r"\+7\d{10}", enabled=False),
    ])

    assert detector.detect("ivan@mail.ru")["data"][0]["class"] == "email"
    assert detector.detect("+79991234567")["data"] == []  # disabled -> не детектится


def test_build_nsfw_unions_words_from_enabled_dicts():
    detector = GuardEngine._build_nsfw([
        SimpleNamespace(text="дурак козёл", enabled=True),
        SimpleNamespace(text="плохое", enabled=False),
    ])

    assert detector.detect("ты ДУРАК")["NSFW_DETECT"] is True
    assert detector.detect("плохое")["NSFW_DETECT"] is False  # из выключенного словаря


def test_build_relevant_splits_text_by_lines_and_skips_disabled():
    detector = GuardEngine._build_relevant([
        SimpleNamespace(type="greeting", text="привет\nздравствуйте", enabled=True),
        SimpleNamespace(type="farewell", text="пока", enabled=False),
    ])

    assert detector.detect("привет")["category"] == "greeting"
    assert detector.detect("пока")["RELEVANT"] is True  # выключенная категория не учитывается
