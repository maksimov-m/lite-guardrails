import pytest

from backend.domain.detectors.relevant import utils
from backend.domain.detectors.relevant.detector import RelevantDetector


@pytest.fixture
def detector():
    return RelevantDetector(
        phrases_by_category={
            "greeting": ["привет"],
            "gratitude": ["спасибо", "спасибо большое"],
        }
    )


def test_pure_chitchat_is_not_relevant(detector):
    result = detector.detect("привет")
    assert result["RELEVANT"] is False
    assert result["category"] == "greeting"


def test_chitchat_prefix_with_real_question_stays_relevant(detector):
    assert detector.detect("привет как настроить роутер дома")["RELEVANT"] is True


def test_gibberish_is_blocked(detector):
    result = detector.detect("!!! ??? :)")
    assert (result["RELEVANT"], result["category"], result["data"]) == (False, "gibberish", [])


def test_longest_phrase_wins_in_alternation(detector):
    assert detector.detect("спасибо большое")["data"][0]["value"] == "спасибо большое"


def test_top_category_is_the_most_frequent(detector):
    assert detector.detect("привет привет спасибо")["category"] == "greeting"


def test_match_offsets_point_at_value(detector):
    item = detector.detect("привет")["data"][0]
    assert "привет"[item["start"] : item["end"]] == item["value"]


def test_read_chitchat_files_groups_by_filename_and_skips_comments(tmp_path):
    (tmp_path / "greeting.txt").write_text(
        "привет\n# комментарий\n\nздравствуйте\n", encoding="utf-8"
    )
    (tmp_path / "notes.md").write_text("пока\n", encoding="utf-8")
    assert utils.read_chitchat_files(str(tmp_path)) == {"greeting": ["привет", "здравствуйте"]}


def test_build_category_patterns_skips_empty_categories():
    patterns = utils.build_category_patterns({"a": ["да"], "empty": []})
    assert set(patterns) == {"a"}
    assert patterns["a"].search("да")
