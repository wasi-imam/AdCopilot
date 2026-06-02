# scorer.py
# Purpose: Calculate viral score (0-100) for any ad copy.
#
# CHANGES FROM PHASE 1 VERSION:
# 1. Config imported     — no hardcoded values
# 2. Cache added         — same ad = instant result, no API call
# 3. Logger added        — print() replaced with proper logging

import os
import json
import time

from groq import Groq
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# --- NEW imports (Phase 2) ---
from config import (
    LLM_MODEL,
    LLM_TEMPERATURE_SCORER,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_AD_WORDS,
    MIN_AD_WORDS,
    WEIGHT_HOOK,
    WEIGHT_SENTIMENT,
    WEIGHT_KEYWORDS,
    WEIGHT_LENGTH,
    WEIGHT_CLARITY,
    MAX_TOKENS_SCORER
)
# WHY: Pehle yeh values scorer.py mein hardcoded thi
# Ab config.py se aati hain — ek jagah se control

from utils.cache import get_cached, set_cache
# WHY: Same ad dobara aaye toh LLM call nahi karni
# Cache se instant result milega

from utils.logger import scorer_logger
# WHY: print() ki jagah proper logging

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ============================================================
# Pydantic Model — same as before
# ============================================================
class AdMetrics(BaseModel):
    hook_strength:       int
    sentiment_stability: int
    keyword_density:     int
    clarity:             int


# ============================================================
# Input Validator — same as Phase 1
# ============================================================
def validate_ad_input(ad_copy: str) -> tuple:
    """
    Validate ad copy before processing.
    Returns: (is_valid: bool, error_message: str)
    """
    if not ad_copy or not ad_copy.strip():
        return False, "Ad copy cannot be empty."

    word_count = len(ad_copy.strip().split())

    if word_count < MIN_AD_WORDS:
        # MIN_AD_WORDS — config.py se aa raha hai
        # Pehle: MIN_AD_LENGTH = 3 hardcoded tha yahan
        return False, f"Ad copy too short — minimum {MIN_AD_WORDS} words required."

    if word_count > MAX_AD_WORDS:
        # MAX_AD_WORDS — config.py se aa raha hai
        # Pehle: MAX_AD_LENGTH = 200 hardcoded tha yahan
        return False, f"Ad copy too long — maximum {MAX_AD_WORDS} words. Your ad: {word_count} words."

    return True, ""


# ============================================================
# JSON Parser — same as Phase 1
# ============================================================
def _parse_llm_json(raw_output: str) -> dict:
    """Safely parse LLM JSON output."""
    cleaned = raw_output.strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                cleaned = part
                break

    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1

    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    return json.loads(cleaned)


# ============================================================
# LLM Metric Extraction — UPGRADED in Phase 2
# WHAT CHANGED:
#   1. Cache check added at the top
#   2. Cache store added before return
#   3. Hardcoded values replaced with config values
#   4. print() replaced with logger
# ============================================================
def extract_metrics_from_llm(ad_copy: str) -> AdMetrics:
    """
    Extract ad metrics using LLM.
    Now checks cache first — skips LLM if already analyzed.
    """

    # --- NEW: Cache check (Phase 2) ---
    # WHY: Agar same ad pehle analyze ho chuka hai
    #      toh LLM call waste hai — cache se lo
    # WHERE: Function ke bilkul shuruwat mein
    cached = get_cached(f"scorer:{ad_copy}")
    # "scorer:" prefix — different functions ki
    # entries mix na ho jaayein cache mein

    if cached:
        scorer_logger.info("Cache hit — scorer skipping LLM call")
        return AdMetrics(**cached)
        # Cached result return karo — zero API call

    # --- Prompt ---
    prompt = f"""You are an expert marketing analyst. Analyze the following ad copy and return a JSON object with exactly these 4 keys:

- hook_strength (integer 1-10): How compelling is the opening line?
- sentiment_stability (integer 1-10): Is the emotional tone consistent?
- keyword_density (integer 1-10): Are relevant keywords naturally included?
- clarity (integer 1-10): Is the core message immediately clear?

Ad Copy: "{ad_copy}"

Return ONLY valid JSON. No explanation. No markdown.
Example: {{"hook_strength": 8, "sentiment_stability": 7, "keyword_density": 6, "clarity": 9}}"""

    # --- Retry loop ---
    last_error = None

    for attempt in range(MAX_RETRIES):
        # MAX_RETRIES — config.py se (pehle hardcoded 3 tha)
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                # CHANGED: "llama-3.3-70b-versatile" → LLM_MODEL from config

                messages=[{"role": "user", "content": prompt}],

                temperature=LLM_TEMPERATURE_SCORER,
                # CHANGED: 0.1 → LLM_TEMPERATURE_SCORER from config

                max_tokens=MAX_TOKENS_SCORER
                # CHANGED: 150 → MAX_TOKENS_SCORER from config (80)
                # Token reduction — sirf JSON chahiye
            )

            raw_output = response.choices[0].message.content.strip()
            parsed     = _parse_llm_json(raw_output)
            metrics    = AdMetrics(**parsed)

            # --- NEW: Store in cache (Phase 2) ---
            # WHY: Next time same ad aaye — cache se milega
            # WHERE: Successful result ke baad, return se pehle
            set_cache(f"scorer:{ad_copy}", parsed)

            return metrics

        except ValidationError as e:
            last_error = f"Invalid types from LLM: {e}"
            scorer_logger.warning(f"Attempt {attempt + 1} failed (validation): {last_error}")

        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON from LLM: {e}"
            scorer_logger.warning(f"Attempt {attempt + 1} failed (JSON): {last_error}")

        except Exception as e:
            last_error = f"API call failed: {e}"
            scorer_logger.warning(f"Attempt {attempt + 1} failed (API): {last_error}")

        if attempt < MAX_RETRIES - 1:
            scorer_logger.info(f"Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            # RETRY_DELAY — config.py se (pehle hardcoded 2 tha)

    # --- Fallback ---
    scorer_logger.error(f"All {MAX_RETRIES} attempts failed. Using fallback metrics.")
    return AdMetrics(
        hook_strength=5,
        sentiment_stability=5,
        keyword_density=5,
        clarity=5
    )


# ============================================================
# Length Score — same as Phase 1, no change
# ============================================================
def calculate_length_score(ad_copy: str) -> int:
    """Calculate length penalty score. Sweet spot: 15-50 words."""
    word_count = len(ad_copy.split())

    if 15 <= word_count <= 50:
        return 10
    elif word_count < 15:
        return max(1, word_count - 5)
    else:
        penalty = (word_count - 50) // 5
        return max(1, 10 - penalty)


# ============================================================
# Main Scoring Function — UPGRADED in Phase 2
# WHAT CHANGED:
#   Hardcoded weight values → config values
# ============================================================
def calculate_viral_score(ad_copy: str) -> dict:
    """
    Calculate complete viral score for an ad.
    Returns dict with score, grade, breakdown.
    """

    # Input validation — same as Phase 1
    is_valid, error_msg = validate_ad_input(ad_copy)
    if not is_valid:
        return {
            "error":       True,
            "error_msg":   error_msg,
            "total_score": 0,
            "grade":       "N/A",
            "word_count":  len(ad_copy.split()) if ad_copy else 0,
            "breakdown": {
                "length_score":        0,
                "hook_strength":       0,
                "sentiment_stability": 0,
                "keyword_density":     0,
                "clarity":             0
            }
        }

    word_count   = len(ad_copy.split())
    length_score = calculate_length_score(ad_copy)
    metrics      = extract_metrics_from_llm(ad_copy)

    # --- CHANGED: Hardcoded weights → config values ---
    # PEHLE:                    # ABHI:
    # W_hook      = 0.30        # W_hook      = WEIGHT_HOOK
    # W_sentiment = 0.20        # W_sentiment = WEIGHT_SENTIMENT
    # W_keywords  = 0.20        # W_keywords  = WEIGHT_KEYWORDS
    # W_length    = 0.15        # W_length    = WEIGHT_LENGTH
    # W_clarity   = 0.15        # W_clarity   = WEIGHT_CLARITY
    #
    # WHY: Config mein ek jagah se sab control hota hai

    raw_score = (
        WEIGHT_LENGTH    * (length_score               * 10) +
        WEIGHT_HOOK      * (metrics.hook_strength      * 10) +
        WEIGHT_SENTIMENT * (metrics.sentiment_stability * 10) +
        WEIGHT_KEYWORDS  * (metrics.keyword_density    * 10) +
        WEIGHT_CLARITY   * (metrics.clarity            * 10)
    )

    final_score = round(raw_score)

    return {
        "error":       False,
        "total_score": final_score,
        "grade":       _get_grade(final_score),
        "word_count":  word_count,
        "breakdown": {
            "length_score":        length_score,
            "hook_strength":       metrics.hook_strength,
            "sentiment_stability": metrics.sentiment_stability,
            "keyword_density":     metrics.keyword_density,
            "clarity":             metrics.clarity
        },
        "weights": {
            "length":    WEIGHT_LENGTH,
            "hook":      WEIGHT_HOOK,
            "sentiment": WEIGHT_SENTIMENT,
            "keywords":  WEIGHT_KEYWORDS,
            "clarity":   WEIGHT_CLARITY
        }
    }


def _get_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 85:
        return "A — Excellent"
    elif score >= 70:
        return "B — Good"
    elif score >= 55:
        return "C — Average"
    elif score >= 40:
        return "D — Needs Work"
    else:
        return "F — Poor"