"""Tests for the file-based cache layer."""

from __future__ import annotations

import json
import time

from seismic_risk.cache import cache_get, cache_put, get_cache_dir


class TestCacheLayer:
    def test_miss_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", tmp_path)
        assert cache_get("nonexistent", max_age_seconds=3600) is None

    def test_put_then_get(self, monkeypatch, tmp_path):
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", tmp_path)
        cache_put("test.bin", b"hello world")
        result = cache_get("test.bin", max_age_seconds=3600)
        assert result == b"hello world"

    def test_expired_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", tmp_path)
        cache_put("old.bin", b"stale data")
        # Backdate the meta timestamp
        meta_path = tmp_path / "old.bin.meta"
        meta_path.write_text(json.dumps({"timestamp": time.time() - 7200}))
        assert cache_get("old.bin", max_age_seconds=3600) is None

    def test_cache_dir_created(self, monkeypatch, tmp_path):
        cache_dir = tmp_path / "sub" / "deep"
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", cache_dir)
        result = get_cache_dir()
        assert result == cache_dir
        assert cache_dir.is_dir()

    def test_different_keys_dont_collide(self, monkeypatch, tmp_path):
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", tmp_path)
        cache_put("a.bin", b"alpha")
        cache_put("b.bin", b"bravo")
        assert cache_get("a.bin", max_age_seconds=3600) == b"alpha"
        assert cache_get("b.bin", max_age_seconds=3600) == b"bravo"

    def test_corrupted_meta_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr("seismic_risk.cache._CACHE_DIR", tmp_path)
        (tmp_path / "bad.bin").write_bytes(b"data")
        (tmp_path / "bad.bin.meta").write_text("not json")
        assert cache_get("bad.bin", max_age_seconds=3600) is None
