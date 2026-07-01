import types

import pytest
from fastapi import HTTPException

from src.entrypoints.detectors.auth import (
    API_KEY_PREFIX,
    generate_api_key,
    hash_key,
    load_api_keys,
    require_api_key,
)


class _Row:
    def __init__(self, id, name, key_hash, enabled=True):
        self.id, self.name, self.key_hash, self.enabled = id, name, key_hash, enabled


class _Repo:
    def __init__(self, rows):
        self._rows = rows

    def list(self):
        return self._rows


def _request(api_keys):
    """Минимальный фейковый Request: только то, что читает require_api_key."""
    state = types.SimpleNamespace(api_keys=api_keys)
    app = types.SimpleNamespace(state=state)
    return types.SimpleNamespace(app=app, state=types.SimpleNamespace())


def test_hash_key_is_deterministic():
    assert hash_key("abc") == hash_key("abc")
    assert hash_key("abc") != hash_key("abd")


def test_generate_api_key_shape():
    raw, key_hash, prefix = generate_api_key()
    assert raw.startswith(API_KEY_PREFIX)
    assert key_hash == hash_key(raw)
    assert raw.startswith(prefix)
    # два вызова дают разные ключи
    assert generate_api_key()[0] != raw


def test_load_api_keys_skips_disabled():
    rows = [
        _Row(1, "alpha", "h1", enabled=True),
        _Row(2, "beta", "h2", enabled=False),
    ]
    keys = load_api_keys(_Repo(rows))
    assert keys == {"h1": {"id": 1, "name": "alpha"}}


def test_require_api_key_valid_sets_state():
    raw, key_hash, _ = generate_api_key()
    req = _request({key_hash: {"id": 7, "name": "alpha"}})
    require_api_key(req, x_api_key=raw)
    assert req.state.api_key == {"id": 7, "name": "alpha"}


def test_require_api_key_missing_rejected():
    req = _request({"h1": {"id": 1, "name": "alpha"}})
    with pytest.raises(HTTPException) as e:
        require_api_key(req, x_api_key="")
    assert e.value.status_code == 401


def test_require_api_key_invalid_rejected():
    req = _request({"h1": {"id": 1, "name": "alpha"}})
    with pytest.raises(HTTPException) as e:
        require_api_key(req, x_api_key="gk_unknown")
    assert e.value.status_code == 401
