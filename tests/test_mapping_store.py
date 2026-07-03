import pytest

from backend.adapters.store import InMemoryMappingStore, RedisMappingStore
from backend.ports.mapping_store import MappingStore


def test_inmemory_store_roundtrips_mapping():
    store = InMemoryMappingStore()
    store.save("abc", {"<EMAIL_1>": "ivan@mail.ru"})
    assert store.get("abc") == {"<EMAIL_1>": "ivan@mail.ru"}


def test_inmemory_store_returns_none_for_unknown_id():
    assert InMemoryMappingStore().get("missing") is None


def test_inmemory_store_isolates_copies():
    store = InMemoryMappingStore()
    original = {"<EMAIL_1>": "ivan@mail.ru"}
    store.save("abc", original)
    original["<EMAIL_1>"] = "changed"
    assert store.get("abc") == {"<EMAIL_1>": "ivan@mail.ru"}


def test_concrete_stores_implement_the_port():
    assert issubclass(InMemoryMappingStore, MappingStore)
    assert issubclass(RedisMappingStore, MappingStore)


def test_port_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        MappingStore()
