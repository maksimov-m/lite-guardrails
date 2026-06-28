import pytest

from src.domain.detectors.nsfw import utils
from src.domain.detectors.nsfw.detector import NsfwDetector


@pytest.fixture
def detector():
    return NsfwDetector(extra_words=["дурак"])


def test_detects_banned_word_with_offsets(detector):
    item = detector.detect("ты дурак")["data"][0]
    assert (item["value"], item["start"], item["end"]) == ("дурак", 3, 8)


def test_detection_is_case_insensitive(detector):
    assert detector.detect("ты ДУРАК")["NSFW_DETECT"] is True


def test_matches_whole_token_only(detector):
    assert detector.detect("придурак")["NSFW_DETECT"] is False


def test_clean_text_has_no_nsfw(detector):
    assert detector.detect("вполне приличный текст") == {"NSFW_DETECT": False, "data": []}


def test_extra_words_extend_the_builtin_set():
    assert NsfwDetector().detect("плохослово123")["NSFW_DETECT"] is False
    extended = NsfwDetector(extra_words=["плохослово123"])
    assert extended.detect("вот плохослово123")["NSFW_DETECT"] is True


def test_builtin_dictionary_is_loaded():
    assert len(NsfwDetector.load_builtin_words()) > 1000


def test_normalize_words_strips_lowercases_and_drops_empty():
    assert utils.normalize_words([" Foo ", "BAR", "  ", ""]) == {"foo", "bar"}


def test_read_txt_dictionaries_merges_only_txt_files(tmp_path):
    (tmp_path / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("gamma\n", encoding="utf-8")
    (tmp_path / "ignore.md").write_text("delta\n", encoding="utf-8")
    assert utils.read_txt_dictionaries(str(tmp_path)) == {"alpha", "beta", "gamma"}


def test_read_txt_dictionaries_requires_a_txt_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        utils.read_txt_dictionaries(str(tmp_path))


def test_read_txt_dictionaries_rejects_empty_dictionaries(tmp_path):
    (tmp_path / "empty.txt").write_text("\n   \n", encoding="utf-8")
    with pytest.raises(ValueError):
        utils.read_txt_dictionaries(str(tmp_path))
