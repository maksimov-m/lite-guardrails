from types import SimpleNamespace

import pytest

from src.domain.detectors.pii.detector import PiiDetector
from src.entrypoints.detectors.detection import (
    anonymize_batch,
    anonymize_text,
    deanonymize_batch,
    deanonymize_text,
)


class FakeStore:
    def __init__(self):
        self._data = {}

    def save(self, key, mapping):
        self._data[key] = mapping

    def get(self, key):
        return self._data.get(key)


@pytest.fixture
def request_ctx():
    state = SimpleNamespace(guard=SimpleNamespace(pii=PiiDetector()), store=FakeStore())
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_anonymize_text_masks_and_saves_mapping(request_ctx):
    result = anonymize_text(request_ctx, "почта ivan@mail.ru")

    assert result["id"] is not None
    assert "ivan@mail.ru" not in result["text"]
    # mapping реально сохранён в стор и восстанавливается обратно
    assert deanonymize_text(request_ctx, result["id"], result["text"]) == "почта ivan@mail.ru"


def test_anonymize_text_without_pii_has_no_id(request_ctx):
    assert anonymize_text(request_ctx, "без пии") == {"id": None, "text": "без пии"}


def test_anonymize_batch_masks_and_assigns_ids(request_ctx):
    results = anonymize_batch(request_ctx, [
        "почта ivan@mail.ru",
        "карта 4012 8888 8888 1881",
        "без пии",
    ])

    assert len(results) == 3
    assert "ivan@mail.ru" not in results[0]["text"] and results[0]["id"]
    assert "4012 8888 8888 1881" not in results[1]["text"] and results[1]["id"]
    assert results[2] == {"id": None, "text": "без пии"}


def test_anonymize_then_deanonymize_batch_roundtrip(request_ctx):
    texts = ["почта ivan@mail.ru", "карта 4012 8888 8888 1881"]

    anonymized = anonymize_batch(request_ctx, texts)
    items = [SimpleNamespace(id=r["id"], text=r["text"]) for r in anonymized]
    restored = deanonymize_batch(request_ctx, items)

    assert [r["text"] for r in restored] == texts
    assert all(r["restored"] for r in restored)


def test_deanonymize_batch_marks_unknown_id_as_not_restored(request_ctx):
    items = [SimpleNamespace(id="missing", text="почта <EMAIL_1>")]

    restored = deanonymize_batch(request_ctx, items)

    assert restored == [{"text": "почта <EMAIL_1>", "restored": False}]
