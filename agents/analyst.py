# analyst.py
# Purpose: Agent 1 — Compare user's ad against competitor ads
# and identify specific gaps as structured JSON.
#
# CHANGES FROM PHASE 1:
# 1. Config imported     — MAX_RETRIES, RETRY_DELAY, LLM_MODEL
#                          hardcoded nahi — config.py se aata hai
# 2. Cache added         — same query dobara aaye toh LLM skip
# 3. Logger added        — print() replaced with analyst_logger
# 4. MAX_RETRIES/DELAY   — file mein define nahi — config se

import os
import json
import time

from groq import Groq
from dotenv import load_dotenv

# Support Streamlit Cloud secrets
try:
    import streamlit as st
    if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

# --- NEW imports (Phase 2) ---
from config import (
    LLM_MODEL,
    LLM_TEMPERATURE_ANALYST,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_TOKENS_ANALYST
)
# WHY: Pehle analyst.py mein yeh tha:
#   MAX_RETRIES = 3   ← hardcoded
#   RETRY_DELAY = 2   ← hardcoded
# Ab config.py se aata hai — ek jagah se control
# scorer.py, analyst.py, builder.py — sab same value use karein

from utils.cache import get_cached, set_cache
# WHY: Agar same user_ad + product_description pehle
#      analyze ho chuka hai — LLM call waste hai
#      Cache se instant result milega

from utils.logger import analyst_logger
# WHY: print() production mein kaam nahi karta
#      Logger — timestamp, level, file save — sab hota hai

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# NOTE: MAX_RETRIES aur RETRY_DELAY ab yahan define nahi hain
# Pehle Phase 1 mein yeh tha:
#   MAX_RETRIES = 3
#   RETRY_DELAY = 2
# Ab config.py se import ho raha hai — upar dekho imports mein


# ============================================================
# _safe_get_similar_ads — SAME AS PHASE 1
# No changes here — already had error handling
# ============================================================
def _safe_get_similar_ads(product_description: str) -> tuple:
    """
    Safely retrieve similar ads from ChromaDB.
    Returns empty list if ChromaDB unavailable.
    """
    try:
        from rag.retriever import get_similar_ads, format_for_agent
        similar_ads = get_similar_ads(product_description, n_results=5)
        context     = format_for_agent(similar_ads)
        return similar_ads, context

    except Exception as e:
        analyst_logger.warning(f"RAG retrieval failed: {e}")
        # CHANGED: print() → analyst_logger.warning()
        # WHY: RAG fail hona unexpected hai — warning level

        analyst_logger.warning("Continuing without competitor context...")
        return [], "No competitor context available — analyzing independently."


# ============================================================
# _parse_gaps_json — SAME AS PHASE 1
# No changes — already safe
# ============================================================
def _parse_gaps_json(raw_output: str) -> list:
    """
    Safely parse LLM JSON array output.
    Handles markdown, extra text, malformed JSON.
    """
    cleaned = raw_output.strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                cleaned = part
                break

    start = cleaned.find("[")
    end   = cleaned.rfind("]") + 1

    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    return json.loads(cleaned)


# ============================================================
# _get_fallback_gaps — SAME AS PHASE 1
# No changes — already good
# ============================================================
def _get_fallback_gaps() -> list:
    """
    Return generic gaps when LLM fails completely.
    Better than crashing — user gets something useful.
    """
    return [
        {
            "gap":             "Unable to complete full analysis — please try again",
            "severity":        "medium",
            "competitor_does": "Analysis service temporarily unavailable"
        },
        {
            "gap":             "Consider adding a clear call-to-action",
            "severity":        "high",
            "competitor_does": "Most successful ads end with Shop Now, Order Today"
        },
        {
            "gap":             "Ensure your hook (first line) is compelling",
            "severity":        "high",
            "competitor_does": "Top ads open with a bold statement or question"
        }
    ]


# ============================================================
# analyze_gaps — MAIN FUNCTION — UPGRADED IN PHASE 2
#
# WHAT CHANGED:
# 1. Cache check added   — function ke shuruwat mein
# 2. Cache store added   — successful result ke baad
# 3. print() → logger   — har jagah
# 4. LLM call mein      — hardcoded values → config values
#
# WHERE exactly:
# Line "NEW PHASE 2" comments se mark kiya hai
# ============================================================
def analyze_gaps(user_ad: str, product_description: str) -> list:
    """
    Compare user's ad against competitor ads.
    Returns list of gap dictionaries.
    Now includes caching and logging.
    """

    # Basic input check — same as Phase 1
    if not user_ad or not user_ad.strip():
        return _get_fallback_gaps()

    if not product_description or not product_description.strip():
        product_description = "general product"

    # --------------------------------------------------------
    # NEW PHASE 2: Cache check
    # WHAT: Pehle check karo cache mein result hai ya nahi
    # WHERE: RAG call se pehle — function ke shuruwat mein
    # WHY: Same ad + same product → same gaps hamesha
    #      LLM call expensive hai — baar baar kyun karein
    # --------------------------------------------------------
    cache_key = f"analyst:{user_ad}:{product_description}"
    # Cache key = "analyst:" + ad text + product description
    # "analyst:" prefix — scorer cache se alag rehta hai
    # Same ad ko scorer ne cache kiya hoga "scorer:..." key se
    # Dono alag hain — mix nahi honge

    cached = get_cached(cache_key)
    if cached:
        analyst_logger.info("Cache hit — analyst skipping LLM call")
        # CHANGED: print() → analyst_logger.info()
        return cached
        # Stored gaps list return karo — zero API call

    # RAG retrieval — same as Phase 1
    similar_ads, competitor_context = _safe_get_similar_ads(product_description)
    rag_available = len(similar_ads) > 0

    # Prompt building — same as Phase 1
    if rag_available:
        prompt = f"""You are a senior marketing analyst with 15 years of experience.

Your task: Compare the USER'S AD against TOP COMPETITOR ADS and identify specific gaps.

USER'S AD:
\"\"\"{user_ad}\"\"\"

{competitor_context}

Identify gaps by comparing user's ad to what competitors do better.
Return ONLY a JSON array with 3 to 6 objects. Each object must have:
- "gap": specific problem (be concrete)
- "severity": exactly "high", "medium", or "low"
- "competitor_does": what competitors do instead

No explanation. No markdown. Only the JSON array."""

    else:
        prompt = f"""You are a senior marketing analyst with 15 years of experience.

Your task: Analyze this ad copy and identify common marketing weaknesses.

USER'S AD:
\"\"\"{user_ad}\"\"\"

Note: No competitor data available — analyze based on general marketing best practices.

Identify 3 to 5 gaps. Return ONLY a JSON array. Each object must have:
- "gap": specific problem found
- "severity": exactly "high", "medium", or "low"
- "competitor_does": what best practice suggests instead

No explanation. No markdown. Only the JSON array."""

    # Retry loop — same structure as Phase 1
    # CHANGED: hardcoded 3 → MAX_RETRIES from config
    # CHANGED: hardcoded 2 → RETRY_DELAY from config
    last_error = None

    for attempt in range(MAX_RETRIES):
        # MAX_RETRIES — config.py se aa raha hai
        # Pehle: range(3) — hardcoded tha
        # Ab: range(MAX_RETRIES) — config se

        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                # CHANGED: "llama-3.3-70b-versatile" → LLM_MODEL
                # WHY: Config mein ek jagah se model change kar sakte hain
                # Pehle: model="llama-3.3-70b-versatile" hardcoded tha

                messages=[
                    {
                        "role": "system",
                        "content": "You are a marketing analyst. Return ONLY valid JSON arrays. No markdown."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                temperature=LLM_TEMPERATURE_ANALYST,
                # CHANGED: 0.2 → LLM_TEMPERATURE_ANALYST from config
                # WHY: Config mein ek jagah se control
                # Analyst low temperature chahiye — consistent output

                max_tokens=MAX_TOKENS_ANALYST
                # CHANGED: 800 → MAX_TOKENS_ANALYST from config (600)
                # WHY: Token reduction — config mein tune kar sakte hain
            )

            raw_output = response.choices[0].message.content.strip()
            gaps       = _parse_gaps_json(raw_output)

            # Validate each gap — same as Phase 1
            validated_gaps = []
            for gap in gaps:
                if not isinstance(gap, dict):
                    continue

                if not all(key in gap for key in ["gap", "severity", "competitor_does"]):
                    continue

                gap["severity"] = str(gap.get("severity", "medium")).lower().strip()
                if gap["severity"] not in ["high", "medium", "low"]:
                    gap["severity"] = "medium"

                validated_gaps.append(gap)

            if not validated_gaps:
                raise ValueError("No valid gaps in LLM response")

            # ----------------------------------------------------
            # NEW PHASE 2: Cache store
            # WHAT: Successful result ko cache mein save karo
            # WHERE: validated_gaps mil gaye — return se pehle
            # WHY: Next time same input aaye → instant result
            # ----------------------------------------------------
            set_cache(cache_key, validated_gaps)
            analyst_logger.info(f"Gaps identified: {len(validated_gaps)}")
            # CHANGED: print() → analyst_logger.info()

            return validated_gaps

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            analyst_logger.warning(f"Attempt {attempt + 1} failed (JSON): {last_error}")
            # CHANGED: print() → analyst_logger.warning()
            # WHY: Retry attempt unexpected hai — warning level

        except ValueError as e:
            last_error = f"Validation error: {e}"
            analyst_logger.warning(f"Attempt {attempt + 1} failed (validation): {last_error}")

        except Exception as e:
            last_error = f"API error: {e}"
            analyst_logger.warning(f"Attempt {attempt + 1} failed (API): {last_error}")

        if attempt < MAX_RETRIES - 1:
            analyst_logger.info(f"Retrying in {RETRY_DELAY}s...")
            # CHANGED: print() → analyst_logger.info()
            time.sleep(RETRY_DELAY)
            # RETRY_DELAY — config.py se (pehle 2 hardcoded tha)

    # All retries failed — fallback
    analyst_logger.error(f"All {MAX_RETRIES} attempts failed. Using fallback gaps.")
    # CHANGED: print() → analyst_logger.error()
    # WHY: Complete failure — error level

    return _get_fallback_gaps()


# ============================================================
# format_gaps_for_display — SAME AS PHASE 1
# No changes needed
# ============================================================
def format_gaps_for_display(gaps: list) -> str:
    """Convert gaps list to readable text for Streamlit."""
    if not gaps:
        return "No significant gaps found. Your ad is competitive!"

    lines = []
    for severity in ["high", "medium", "low"]:
        severity_gaps = [g for g in gaps if g["severity"] == severity]
        for gap in severity_gaps:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[severity]
            lines.append(f"{icon} [{severity.upper()}] {gap['gap']}")
            lines.append(f"   Competitors do: {gap['competitor_does']}")
            lines.append("")

    return "\n".join(lines)