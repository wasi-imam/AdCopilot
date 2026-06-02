# cache.py
# Purpose: Cache LLM responses to avoid duplicate API calls.
#
# HOW IT WORKS:
# 1. Input text ka hash banao (unique fingerprint)
# 2. Hash already cache mein hai? Return stored result
# 3. Nahi hai? LLM call karo, result store karo
#
# TWO LEVELS:
# Level 1 — In-memory cache  : RAM mein, instant access
# Level 2 — Persistent cache : Disk pe, survives restarts
#
# WHY TWO LEVELS:
# Memory only  — app restart pe sab gone
# Disk only    — slow read/write
# Both together — fast + persistent

import hashlib
# hashlib — hashing library
# Purpose: Convert any text into fixed-length fingerprint
# "Run faster" → "a3f8c2d1..." (always same for same input)

import json
import time
import os
from config import CACHE_EXPIRY_SECONDS, CACHE_FILE_PATH
# Import from config — not hardcoded here


# ============================================================
# In-memory store — Python dictionary
# Lives in RAM — resets on app restart
# ============================================================
_memory_cache = {}
# Key   : MD5 hash of input text
# Value : {"result": ..., "timestamp": ...}


# ============================================================
# FUNCTION: Generate cache key
# ============================================================
def _make_key(input_text: str) -> str:
    """
    Convert input text to fixed-length MD5 hash.

    WHY MD5:
    - Fast — hashing is instant
    - Deterministic — same input always gives same hash
    - Fixed length — "short text" and "very long text..."
      both become 32-character strings
    - Not for security — just for cache key lookup

    Example:
    "Run faster shop now" → "a3f8c2d1b4e5f678..."
    """
    return hashlib.md5(input_text.encode("utf-8")).hexdigest()
    # .encode("utf-8") — string to bytes (md5 needs bytes)
    # .hexdigest()     — bytes to hex string


# ============================================================
# FUNCTION: Load persistent cache from disk
# ============================================================
def _load_disk_cache() -> dict:
    """
    Load cache from disk file.
    Returns empty dict if file doesn't exist.
    Called once when module is imported.
    """
    if not os.path.exists(CACHE_FILE_PATH):
        return {}
        # File nahi hai — fresh start

    try:
        with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # File corrupt ho gayi — fresh start
        return {}


# ============================================================
# FUNCTION: Save cache to disk
# ============================================================
def _save_disk_cache(cache_data: dict) -> None:
    """
    Save current cache to disk file.
    Called after every new cache entry.
    """
    try:
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
            # indent=2 — readable JSON format
    except Exception as e:
        print(f"Cache save failed: {e}")
        # Save fail hua — koi baat nahi
        # Memory cache still works


# Load disk cache into memory on startup
_disk_cache = _load_disk_cache()
# Yeh line module import hone pe ek baar chalti hai
# Disk se load karke _disk_cache mein rakh do


# ============================================================
# MAIN FUNCTION: Get cached result
# ============================================================
def get_cached(input_text: str):
    """
    Check if we have a cached result for this input.

    Checks memory first (fast), then disk (persistent).
    Returns None if not found or expired.

    WHY CHECK MEMORY FIRST:
    Memory access = nanoseconds
    Disk access   = milliseconds
    Always check fast store first.
    """
    key = _make_key(input_text)

    # --- Level 1: Memory cache ---
    if key in _memory_cache:
        entry = _memory_cache[key]
        age   = time.time() - entry["timestamp"]
        # age = kitne seconds purana hai

        if age <= CACHE_EXPIRY_SECONDS:
            # Valid — return it
            return entry["result"]
        else:
            # Expired — remove from memory
            del _memory_cache[key]

    # --- Level 2: Disk cache ---
    if key in _disk_cache:
        entry = _disk_cache[key]
        age   = time.time() - entry["timestamp"]

        if age <= CACHE_EXPIRY_SECONDS:
            # Valid — load into memory for next time
            _memory_cache[key] = entry
            return entry["result"]
        else:
            # Expired — remove from disk cache
            del _disk_cache[key]
            _save_disk_cache(_disk_cache)

    return None
    # Cache miss — caller will make LLM call


# ============================================================
# MAIN FUNCTION: Store result in cache
# ============================================================
def set_cache(input_text: str, result) -> None:
    """
    Store a result in both memory and disk cache.
    """
    key   = _make_key(input_text)
    entry = {
        "result":    result,
        "timestamp": time.time()
        # time.time() — current Unix timestamp (seconds since 1970)
    }

    # Store in memory
    _memory_cache[key] = entry

    # Store on disk
    _disk_cache[key] = entry
    _save_disk_cache(_disk_cache)


# ============================================================
# UTILITY: Cache statistics
# ============================================================
def get_cache_stats() -> dict:
    """Return cache statistics for debugging."""
    return {
        "memory_entries": len(_memory_cache),
        "disk_entries":   len(_disk_cache),
        "cache_file":     CACHE_FILE_PATH
    }


def clear_cache() -> None:
    """Clear all cache — memory and disk."""
    global _memory_cache, _disk_cache
    _memory_cache = {}
    _disk_cache   = {}
    if os.path.exists(CACHE_FILE_PATH):
        os.remove(CACHE_FILE_PATH)
    print("Cache cleared.")