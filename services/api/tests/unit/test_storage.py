from pathlib import Path

import pytest

from app.services.storage import LocalStorage, StorageError


def test_roundtrip(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    store.put("uploads/a/b.txt", b"hello")
    assert store.exists("uploads/a/b.txt")
    assert store.get("uploads/a/b.txt") == b"hello"
    store.delete("uploads/a/b.txt")
    assert not store.exists("uploads/a/b.txt")


@pytest.mark.parametrize("key", ["", "../escape.txt", "/abs.txt", "a/../../b", "a\\b"])
def test_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(StorageError):
        LocalStorage(tmp_path).put(key, b"x")
