# explainable_scorer.py
# Purpose: Explainable scoring system — 6 dimensions with
#          reasons, evidence, and improvement suggestions.
#
# KEY DESIGN DECISIONS:
# 1. Separate file — existing scorer.py untouched
# 2. Deterministic: clarity + length (no LLM cost)
# 3. LLM: hook, value, cta, emotion (needs judgment)
# 4. Single LLM call — all 4 LLM dimensions at once
# 5. Pydantic validation — structured output guaranteed

import os
import json
import time
import math

from groq import Groq
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

try:
    import streamlit as st
    if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

from config import (
    LLM_MODEL,
    LLM_TEMPERATURE_SCORER,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_TOKENS_EXPLAINER,
    EXPL_WEIGHT_HOOK,
    EXPL_WEIGHT_VALUE,
    EXPL_WEIGHT_CTA,
    EXPL_WEIGHT_EMOTION,
    EXPL_WEIGHT_CLARITY,
    EXPL_WEIGHT_LENGTH,
)
from utils.cache import get_cached, set_cache
from utils.logger import scorer_logger

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ============================================================
# Pydantic Models — strict structure
# ============================================================

class DimensionScore(BaseModel):
    score:      int    # 1-10
    reason:     str    # WHY this score
    evidence:   str    # exact text from ad
    suggestion: str    # HOW to improve

class LLMDimensions(BaseModel):
    hook:     DimensionScore
    value:    DimensionScore
    cta:      DimensionScore
    emotion:  DimensionScore


# ============================================================
# DETERMINISTIC FUNCTIONS — no LLM, always same output
# ============================================================

def _calculate_clarity_score(ad_copy: str) -> dict:
    """
    Flesch Reading Ease formula — deterministic.
    Higher score = easier to read.

    Formula:
    FRE = 206.835
          - 1.015  * (words / sentences)
          - 84.6   * (syllables / words)

    FRE >= 70  → clarity = 8-10 (easy)
    FRE 50-70  → clarity = 5-7  (medium)
    FRE < 50   → clarity = 1-4  (hard)
    """
    words     = ad_copy.split()
    sentences = [s.strip() for s in ad_copy.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    word_count     = len(words)
    sentence_count = max(len(sentences), 1)

    # Count syllables — simple rule: vowel groups per word
    def count_syllables(word):
        word = word.lower().strip(".,!?\"'")
        vowels = "aeiou"
        count  = 0
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        return max(count, 1)

    syllable_count = sum(count_syllables(w) for w in words)

    # Flesch Reading Ease
    fre = (206.835
           - 1.015  * (word_count / sentence_count)
           - 84.6   * (syllable_count / max(word_count, 1)))

    fre = max(0, min(100, fre))  # clamp 0-100

    # Convert FRE to 1-10 score
    if fre >= 80:
        score = 10
        rating = "Excellent"
        reason = "Very easy to read — clear and simple language."
    elif fre >= 70:
        score = 8
        rating = "Good"
        reason = "Easy to read — most people will understand instantly."
    elif fre >= 60:
        score = 6
        rating = "Average"
        reason = "Fairly easy — some sentences could be shorter."
    elif fre >= 50:
        score = 4
        rating = "Poor"
        reason = "Moderate difficulty — simplify sentence structure."
    else:
        score = 2
        rating = "Poor"
        reason = "Hard to read — too complex for ad copy."

    suggestion = (
        "Use shorter sentences (under 15 words). "
        "Replace complex words with simple ones."
        if score < 7 else
        "Clarity is good — maintain this simplicity."
    )

    return {
        "dimension":  "Clarity & Readability",
        "score":      score,
        "weight":     EXPL_WEIGHT_CLARITY,
        "weighted":   round(score * EXPL_WEIGHT_CLARITY * 10, 1),
        "rating":     rating,
        "reason":     reason,
        "evidence":   ad_copy[:80] + "..." if len(ad_copy) > 80 else ad_copy,
        "suggestion": suggestion,
        "fre_score":  round(fre, 1)
    }


def _calculate_length_score(ad_copy: str) -> dict:
    """
    Word count based scoring — deterministic.
    Sweet spot: 15-50 words for ad copy.
    """
    word_count = len(ad_copy.split())

    if 15 <= word_count <= 50:
        score      = 10
        rating     = "Excellent"
        reason     = "Perfect length — concise and complete."
        suggestion = "Maintain this length."
    elif 10 <= word_count < 15:
        score      = 6
        rating     = "Average"
        reason     = "Slightly short — may lack key details."
        suggestion = "Add one more benefit or CTA detail."
    elif 50 < word_count <= 80:
        score      = 6
        rating     = "Average"
        reason     = "Slightly long — reader may lose interest."
        suggestion = "Cut filler words — aim for under 50 words."
    elif word_count < 10:
        score      = 2
        rating     = "Poor"
        reason     = "Too short — not enough information."
        suggestion = "Add hook, benefit, and CTA — minimum 15 words."
    else:
        score      = 2
        rating     = "Poor"
        reason     = "Too long for ad copy — over 80 words."
        suggestion = "Cut to under 50 words — keep only the strongest points."

    return {
        "dimension":  "Length Optimization",
        "score":      score,
        "weight":     EXPL_WEIGHT_LENGTH,
        "weighted":   round(score * EXPL_WEIGHT_LENGTH * 10, 1),
        "rating":     rating,
        "reason":     reason,
        "evidence":   "{} words".format(word_count),
        "suggestion": suggestion,
        "word_count": word_count
    }


# ============================================================
# LLM FUNCTION — single call for 4 dimensions
# ============================================================

def _extract_llm_dimensions(ad_copy: str) -> LLMDimensions:
    """
    Single LLM call — extract all 4 subjective dimensions.
    Returns validated LLMDimensions Pydantic object.
    """
    prompt = """You are an expert advertising analyst. Analyze this ad copy across 4 dimensions.

AD COPY:
"{ad}"

Return ONLY a valid JSON object with exactly this structure:
{{
  "hook": {{
    "score": <1-10>,
    "reason": "<why this score — be specific>",
    "evidence": "<exact phrase from ad that shows this>",
    "suggestion": "<one specific actionable improvement>"
  }},
  "value": {{
    "score": <1-10>,
    "reason": "<why this score — does it answer 'why buy this'>",
    "evidence": "<exact phrase from ad>",
    "suggestion": "<one specific actionable improvement>"
  }},
  "cta": {{
    "score": <1-10>,
    "reason": "<why this score — is it urgent and specific>",
    "evidence": "<exact phrase from ad>",
    "suggestion": "<one specific actionable improvement>"
  }},
  "emotion": {{
    "score": <1-10>,
    "reason": "<why this score — what emotion does it trigger>",
    "evidence": "<exact phrase from ad>",
    "suggestion": "<one specific actionable improvement>"
  }}
}}

Scoring guide:
- hook:   Is the first line compelling? Does it create curiosity or urgency?
- value:  Does it clearly answer "why should I buy this"?
- cta:    Is there a clear, urgent call to action?
- emotion: Does it trigger desire, fear of missing out, or social proof?

No explanation. No markdown. Only the JSON object.""".format(ad=ad_copy)

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE_SCORER,
                max_tokens=MAX_TOKENS_EXPLAINER
            )

            raw = response.choices[0].message.content.strip()

            # Clean markdown if present
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        raw = part
                        break

            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]

            parsed  = json.loads(raw)
            dims    = LLMDimensions(**parsed)
            return dims

        except (ValidationError, json.JSONDecodeError) as e:
            last_error = str(e)
            scorer_logger.warning("Explainer attempt {} failed: {}".format(attempt+1, e))
        except Exception as e:
            last_error = str(e)
            scorer_logger.warning("Explainer API attempt {} failed: {}".format(attempt+1, e))

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    # Fallback — neutral scores
    scorer_logger.error("Explainer all retries failed. Using fallback.")
    fallback = DimensionScore(
        score=5,
        reason="Analysis unavailable — please try again.",
        evidence="N/A",
        suggestion="Re-run analysis for detailed feedback."
    )
    return LLMDimensions(hook=fallback, value=fallback, cta=fallback, emotion=fallback)


# ============================================================
# ASSEMBLY — combine deterministic + LLM
# ============================================================

def _get_rating(score: int) -> str:
    if score >= 9:  return "Excellent"
    if score >= 7:  return "Good"
    if score >= 5:  return "Average"
    if score >= 3:  return "Poor"
    return "Very Poor"


def _get_grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "F"


def _build_one_liner(dimensions: list) -> str:
    """Generate a one-line summary of strongest and weakest dimensions."""
    sorted_dims = sorted(dimensions, key=lambda x: x["score"])
    weakest  = sorted_dims[0]["dimension"]
    strongest = sorted_dims[-1]["dimension"]
    return "Strong {} — Weak {}".format(strongest, weakest)


def _get_top_fixes(dimensions: list) -> list:
    """Top 3 priority fixes — lowest scored dimensions first."""
    sorted_dims = sorted(dimensions, key=lambda x: x["score"])
    fixes = []
    for i, dim in enumerate(sorted_dims[:3]):
        expected_gain = (10 - dim["score"]) * dim["weight"] * 10
        fixes.append({
            "priority":  i + 1,
            "dimension": dim["dimension"],
            "action":    dim["suggestion"],
            "impact":    "+{:.0f} to +{:.0f} pts expected".format(
                expected_gain * 0.7, expected_gain
            )
        })
    return fixes


# ============================================================
# MAIN FUNCTION
# ============================================================

def calculate_explainable_score(ad_copy: str) -> dict:
    """
    Main function — returns complete explainable score.

    Returns:
        dict with total_score, grade, one_liner,
        dimensions (6 items), top_3_fixes
    """
    # Input validation
    if not ad_copy or not ad_copy.strip():
        return {"error": True, "error_msg": "Ad copy cannot be empty."}

    word_count = len(ad_copy.strip().split())
    if word_count < 3:
        return {"error": True, "error_msg": "Ad too short — minimum 3 words."}

    # Cache check
    cache_key = "explainer:{}".format(ad_copy)
    cached = get_cached(cache_key)
    if cached:
        scorer_logger.info("Explainer cache hit")
        return cached

    # Step 1 — Deterministic (no LLM)
    clarity_dim = _calculate_clarity_score(ad_copy)
    length_dim  = _calculate_length_score(ad_copy)

    # Step 2 — LLM (single call for 4 dimensions)
    llm_dims = _extract_llm_dimensions(ad_copy)

    # Step 3 — Build dimension list
    dimensions = [
        {
            "dimension":  "Hook Strength",
            "score":      llm_dims.hook.score,
            "weight":     EXPL_WEIGHT_HOOK,
            "weighted":   round(llm_dims.hook.score * EXPL_WEIGHT_HOOK * 10, 1),
            "rating":     _get_rating(llm_dims.hook.score),
            "reason":     llm_dims.hook.reason,
            "evidence":   llm_dims.hook.evidence,
            "suggestion": llm_dims.hook.suggestion,
        },
        {
            "dimension":  "Value Proposition",
            "score":      llm_dims.value.score,
            "weight":     EXPL_WEIGHT_VALUE,
            "weighted":   round(llm_dims.value.score * EXPL_WEIGHT_VALUE * 10, 1),
            "rating":     _get_rating(llm_dims.value.score),
            "reason":     llm_dims.value.reason,
            "evidence":   llm_dims.value.evidence,
            "suggestion": llm_dims.value.suggestion,
        },
        {
            "dimension":  "Call to Action",
            "score":      llm_dims.cta.score,
            "weight":     EXPL_WEIGHT_CTA,
            "weighted":   round(llm_dims.cta.score * EXPL_WEIGHT_CTA * 10, 1),
            "rating":     _get_rating(llm_dims.cta.score),
            "reason":     llm_dims.cta.reason,
            "evidence":   llm_dims.cta.evidence,
            "suggestion": llm_dims.cta.suggestion,
        },
        {
            "dimension":  "Emotional Trigger",
            "score":      llm_dims.emotion.score,
            "weight":     EXPL_WEIGHT_EMOTION,
            "weighted":   round(llm_dims.emotion.score * EXPL_WEIGHT_EMOTION * 10, 1),
            "rating":     _get_rating(llm_dims.emotion.score),
            "reason":     llm_dims.emotion.reason,
            "evidence":   llm_dims.emotion.evidence,
            "suggestion": llm_dims.emotion.suggestion,
        },
        clarity_dim,
        length_dim,
    ]

    # Step 4 — Total score
    total = sum(d["weighted"] for d in dimensions)
    total = round(min(100, max(0, total)))

    # Step 5 — Assemble result
    result = {
        "error":       False,
        "total_score": total,
        "grade":       _get_grade(total),
        "one_liner":   _build_one_liner(dimensions),
        "word_count":  word_count,
        "dimensions":  dimensions,
        "top_3_fixes": _get_top_fixes(dimensions),
    }

    # Cache store
    set_cache(cache_key, result)
    scorer_logger.info("Explainable score: {}".format(total))

    return result
