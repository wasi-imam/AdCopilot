"""
tests/test_cache.py
Tests for the two-level cache (utils/cache.py)
 
Tera cache.py mein actual function names:
  - get_cached(input_text)         ← get karna
  - set_cache(input_text, result)  ← set karna
  - _make_key(input_text)          ← MD5 key banana (private)
 
Note: _make_key prefix nahi leta — sirf input_text se key banata hai.
      get_cached/set_cache internally prefix handle karte hain ya nahi
      ye teri actual implementation pe depend karta hai.
      Tests accordingly likhे hain.
"""
 
import pytest
import time
import os
import json
 
 
# ─────────────────────────────────────────────
# GROUP 1 — Basic store and retrieve
# ─────────────────────────────────────────────
 
class TestCacheBasics:
    """Cache must store values and return them correctly."""
 
    def test_set_and_get_returns_same_value(self):
        """Value stored must be exactly the value retrieved."""
        from utils.cache import set_cache, get_cached
        set_cache("buy now limited offer test unique 123", {"score": 75})
        result = get_cached("buy now limited offer test unique 123")
        assert result == {"score": 75}, "Expected score 75, got {}".format(result)
 
    def test_get_nonexistent_key_returns_none(self):
        """Asking for something never stored should return None, not crash."""
        from utils.cache import get_cached
        result = get_cached("this ad was absolutely never stored anywhere ever xyz987")
        assert result is None, "Expected None for missing key, got {}".format(result)
 
    def test_overwrite_updates_value(self):
        """Storing same key twice — second value should win."""
        from utils.cache import set_cache, get_cached
        set_cache("overwrite test ad text unique abc", {"score": 60})
        set_cache("overwrite test ad text unique abc", {"score": 80})
        result = get_cached("overwrite test ad text unique abc")
        assert result == {"score": 80}, "Expected 80 after overwrite, got {}".format(result)
 
    def test_different_content_different_result(self):
        """Two different ads must not return each other's cached results."""
        from utils.cache import set_cache, get_cached
        set_cache("ad one about shoes unique test 111", {"score": 55})
        set_cache("ad two about phones unique test 222", {"score": 90})
        assert get_cached("ad one about shoes unique test 111") == {"score": 55}
        assert get_cached("ad two about phones unique test 222") == {"score": 90}
 
 
# ─────────────────────────────────────────────
# GROUP 2 — MD5 key consistency
# ─────────────────────────────────────────────
 
class TestCacheKeyGeneration:
    """_make_key must be deterministic — same input always same key."""
 
    def test_same_input_generates_same_key(self):
        """Same text passed twice — MD5 must be identical."""
        from utils.cache import _make_key
        key1 = _make_key("buy now limited offer today")
        key2 = _make_key("buy now limited offer today")
        assert key1 == key2, "Same input must always generate same MD5 key"
 
    def test_different_input_generates_different_key(self):
        """Different texts must generate different MD5 keys."""
        from utils.cache import _make_key
        key1 = _make_key("buy shoes now")
        key2 = _make_key("buy phones now")
        assert key1 != key2, "Different inputs must not collide on MD5 key"
 
    def test_key_is_string(self):
        """Cache key must be a string (for JSON serialization in disk cache)."""
        from utils.cache import _make_key
        key = _make_key("any ad text here for testing")
        assert isinstance(key, str), "Key must be str, got {}".format(type(key))
 
 
# ─────────────────────────────────────────────
# GROUP 3 — Cache expiry tests
# ─────────────────────────────────────────────
 
class TestCacheExpiry:
    """Cache has expiry — stale entries must not be returned."""
 
    def test_fresh_cache_entry_is_returned(self):
        """A newly stored entry must be retrievable immediately."""
        from utils.cache import set_cache, get_cached
        set_cache("fresh ad text here today unique test 999", {"rewritten": "new ad"})
        result = get_cached("fresh ad text here today unique test 999")
        assert result is not None, "Fresh cache entry should not be expired"
        assert result == {"rewritten": "new ad"}
 
    def test_expired_entry_returns_none(self):
        """
        Entry stored with a past timestamp must return None.
        Hum disk cache mein directly expired entry inject karte hain.
        """
        from utils.cache import _make_key, get_cached
        from config import CACHE_FILE_PATH, CACHE_EXPIRY_SECONDS
 
        test_text = "expired ad text for testing only unique 777"
        cache_key = _make_key(test_text)
        expired_timestamp = time.time() - CACHE_EXPIRY_SECONDS - 100
 
        try:
            # Load existing disk cache
            if os.path.exists(CACHE_FILE_PATH):
                with open(CACHE_FILE_PATH, "r") as f:
                    disk_cache = json.load(f)
            else:
                disk_cache = {}
 
            # Inject expired entry directly into disk cache
            disk_cache[cache_key] = {
                "value": {"score": 99},
                "timestamp": expired_timestamp
            }
            with open(CACHE_FILE_PATH, "w") as f:
                json.dump(disk_cache, f)
 
            # Try to retrieve — must return None (expired)
            result = get_cached(test_text)
            assert result is None, (
                "Expired entry should return None, got {}".format(result)
            )
 
        finally:
            # Cleanup — test entry hatao taaki doosre tests affect na hon
            if os.path.exists(CACHE_FILE_PATH):
                with open(CACHE_FILE_PATH, "r") as f:
                    disk_cache = json.load(f)
                disk_cache.pop(cache_key, None)
                with open(CACHE_FILE_PATH, "w") as f:
                    json.dump(disk_cache, f)
 