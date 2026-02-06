"""Simple file-based cache with TTL expiry."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "seismic-risk"

# TTLs in seconds
AIRPORTS_TTL = 86400  # 24 hours
COUNTRIES_TTL = 604800  # 7 days


def get_cache_dir() -> Path:
    """Return the cache directory, creating it if needed."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def cache_get(key: str, max_age_seconds: int) -> bytes | None:
    """Return cached bytes if fresh, else None."""
    cache_dir = get_cache_dir()
    data_path = cache_dir / key
    meta_path = cache_dir / f"{key}.meta"

    if not data_path.exists() or not meta_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text())
        if time.time() - meta["timestamp"] > max_age_seconds:
            logger.debug("Cache expired for %s", key)
            return None
    except (json.JSONDecodeError, KeyError):
        return None

    logger.debug("Cache hit for %s", key)
    return data_path.read_bytes()


def cache_put(key: str, data: bytes) -> None:
    """Store bytes in cache with current timestamp."""
    cache_dir = get_cache_dir()
    (cache_dir / key).write_bytes(data)
    (cache_dir / f"{key}.meta").write_text(
        json.dumps({"timestamp": time.time()})
    )
    logger.debug("Cached %s (%d bytes)", key, len(data))
