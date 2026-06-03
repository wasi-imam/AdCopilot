# builder.py
# Purpose: Agent 2 — Rewrite ad copy based on analyst gaps.
#
# CHANGES FROM PHASE 1:
# 1. Config imported     — MAX_RETRIES, RETRY_DELAY, LLM_MODEL
#                          hardcoded nahi — config.py se aata hai
# 2. Cache added         — same ad + same gaps dobara aaye toh LLM skip
# 3. Logger added        — print() replaced with builder_logger
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
    LLM_TEMPERATURE_BUILDER,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_TOKENS_BUILDER
)
# WHY: Pehle builder.py mein yeh tha:
#   MAX_RETRIES = 3   ← hardcoded
#   RETRY_DELAY = 2   ← hardcoded
# Ab config.py se aata hai — ek jagah se control
# Scorer, analyst, builder — teeno same value use karein

from utils.cache import get_cached, set_cache
# WHY: Same original_ad + same gaps → same rewrite hoga
# LLM call baar baar kyun karein — cache se lo

from utils.logger import builder_logger
# WHY: print() production mein kaam nahi karta
# Logger — timestamp, level, file save — sab hota hai

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# NOTE: MAX_RETRIES aur RETRY_DELAY ab yahan define nahi hain
# Pehle Phase 1 mein yeh tha:
#   MAX_RETRIES = 3
#   RETRY_DELAY = 2
# Ab config.py se import ho raha hai — upar dekho imports mein


# ============================================================
# rewrite_ad — MAIN FUNCTION — UPGRADED IN PHASE 2
#
# WHAT CHANGED:
# 1. Cache check added   — function ke shuruwat mein
# 2. Cache store added   — successful result ke baad
# 3. print() → logger   — har jagah
# 4. LLM call mein      — hardcoded values → config values
#
# WHERE exactly:
# "NEW PHASE 2" comments se mark kiya hai
# ============================================================
def rewrite_ad(original_ad: str, gaps: list) -> dict:
    """
    Rewrite ad copy to fix identified gaps.
    Now includes caching and logging.

    Parameters:
        original_ad : str  — original ad copy
        gaps        : list — gaps from analyst agent

    Returns:
        dict with rewritten_ad, changes_made, word_count
    """

    # Edge case — no gaps found, same as Phase 1
    if not gaps:
        return {
            "rewritten_ad": original_ad,
            "changes_made": "No gaps identified — original ad returned unchanged.",
            "word_count":   len(original_ad.split())
        }

    # --------------------------------------------------------
    # NEW PHASE 2: Cache check
    # WHAT: Pehle check karo cache mein result hai ya nahi
    # WHERE: Gap instructions banane se pehle — shuruwat mein
    # WHY: Same ad + same gaps → same rewrite hoga
    #      Builder ka LLM call sabse expensive hai (~500 tokens)
    #      Cache se instant result — zero cost
    # --------------------------------------------------------
    gaps_as_string = json.dumps(gaps, sort_keys=True)
    # json.dumps() — gaps list ko string mein convert karo
    # sort_keys=True — keys alphabetically sort karo
    # WHY sort_keys: ["gap A", "gap B"] aur ["gap B", "gap A"]
    # same gaps hain — same cache entry use karni chahiye
    # sort_keys ensure karta hai same result same key bane

    cache_key = f"builder:{original_ad}:{gaps_as_string}"
    # "builder:" prefix — analyst cache se alag rehta hai
    # original_ad + gaps — dono milke unique key bante hain

    cached = get_cached(cache_key)
    if cached:
        builder_logger.info("Cache hit — builder skipping LLM call")
        # CHANGED: print() → builder_logger.info()
        return cached
        # Stored result return karo — zero API call

    # Format gap instructions — same as Phase 1
    # .get() use kiya — safe access, crash nahi hoga
    gap_instructions = ""
    for i, gap in enumerate(gaps, 1):
        severity  = gap.get("severity",        "medium").upper()
        gap_text  = gap.get("gap",             "Improve the ad")
        reference = gap.get("competitor_does", "Follow best practices")

        gap_instructions += f"{i}. [{severity}] Fix: {gap_text}\n"
        gap_instructions += f"   Reference: {reference}\n\n"

    # Prompt — same as Phase 1
    prompt = f"""You are a world-class copywriter specializing in high-converting digital ads.

Rewrite the following ad to fix all identified gaps while preserving the product's identity.

ORIGINAL AD:
\"\"\"{original_ad}\"\"\"

GAPS TO FIX:
{gap_instructions}

RULES:
1. Fix ALL gaps listed above
2. Keep the same product — do not change what is being sold
3. Keep between 20 and 55 words
4. First line must be a stronger hook
5. End with a clear call-to-action

After the rewritten ad, add "---" then list changes as bullet points starting with "CHANGES:".

Format:
[Rewritten ad here]
---
CHANGES:
- Change 1
- Change 2"""

    # Retry loop
    # CHANGED: hardcoded 3 → MAX_RETRIES from config
    # CHANGED: hardcoded 2 → RETRY_DELAY from config
    last_error = None

    for attempt in range(MAX_RETRIES):
        # MAX_RETRIES — config.py se aa raha hai
        # Pehle: range(3) hardcoded tha

        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                # CHANGED: "llama-3.3-70b-versatile" → LLM_MODEL
                # WHY: Config mein ek jagah se model change kar sakte hain

                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert copywriter. Follow format instructions exactly."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                temperature=LLM_TEMPERATURE_BUILDER,
                # CHANGED: 0.7 → LLM_TEMPERATURE_BUILDER from config
                # WHY: Config se control — builder creative hona chahiye
                # Analyst 0.2 (analytical) — builder 0.7 (creative)

                max_tokens=MAX_TOKENS_BUILDER
                # CHANGED: 500 → MAX_TOKENS_BUILDER from config
                # WHY: Config mein tune kar sakte hain
            )

            raw_output = response.choices[0].message.content.strip()

            # Response parsing — same as Phase 1
            if "---" in raw_output:
                parts        = raw_output.split("---", 1)
                rewritten_ad = parts[0].strip()
                changes_raw  = parts[1].strip()

                if "CHANGES:" in changes_raw:
                    changes_text = changes_raw.replace("CHANGES:", "").strip()
                else:
                    changes_text = changes_raw

            else:
                # Separator nahi mila — poora output ad maano
                rewritten_ad = raw_output
                changes_text = "Ad rewritten to address identified gaps."

            # Validation — same as Phase 1
            if not rewritten_ad.strip():
                raise ValueError("Builder returned empty ad copy")

            # Build result dict
            result = {
                "rewritten_ad": rewritten_ad,
                "changes_made": changes_text,
                "word_count":   len(rewritten_ad.split())
            }

            # ----------------------------------------------------
            # NEW PHASE 2: Cache store
            # WHAT: Successful result ko cache mein save karo
            # WHERE: Result ban gaya — return se pehle
            # WHY: Next time same input aaye → instant result
            # ----------------------------------------------------
            set_cache(cache_key, result)
            builder_logger.info("Rewrite complete — result cached.")
            # CHANGED: print() → builder_logger.info()

            return result

        except ValueError as e:
            last_error = f"Validation: {e}"
            builder_logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
            # CHANGED: print() → builder_logger.warning()
            # WHY: Retry attempt — warning level

        except Exception as e:
            last_error = f"API error: {e}"
            builder_logger.warning(f"Attempt {attempt + 1} failed: {last_error}")

        if attempt < MAX_RETRIES - 1:
            builder_logger.info(f"Retrying in {RETRY_DELAY}s...")
            # CHANGED: print() → builder_logger.info()
            time.sleep(RETRY_DELAY)
            # RETRY_DELAY — config.py se (pehle 2 hardcoded tha)

    # All retries failed — fallback
    builder_logger.error(
        f"Builder failed after {MAX_RETRIES} attempts. Returning original."
    )
    # CHANGED: print() → builder_logger.error()
    # WHY: Complete failure — error level

    return {
        "rewritten_ad": original_ad,
        "changes_made": f"Rewrite unavailable — original returned.\nError: {last_error}",
        "word_count":   len(original_ad.split())
    }


# ============================================================
# run_full_pipeline — UPGRADED IN PHASE 2
#
# WHAT CHANGED:
# 1. Logger added — print() replaced
# 2. success flag same as Phase 1 — no change needed
# ============================================================
def run_full_pipeline(user_ad: str, product_description: str) -> dict:
    """
    Run complete 2-agent pipeline: Analyst → Builder.
    Returns error info instead of crashing.
    """
    from agents.analyst import analyze_gaps
    # Import here — circular import se bachne ke liye

    try:
        builder_logger.info("Agent 1 (Analyst) running...")
        # CHANGED: print() → builder_logger.info()

        gaps = analyze_gaps(user_ad, product_description)

        builder_logger.info(f"Gaps identified: {len(gaps)}")

        builder_logger.info("Agent 2 (Builder) running...")

        result = rewrite_ad(original_ad=user_ad, gaps=gaps)

        builder_logger.info("Pipeline complete.")

        return {
            "success":      True,
            "gaps":         gaps,
            "rewritten_ad": result["rewritten_ad"],
            "changes_made": result["changes_made"],
            "word_count":   result["word_count"]
        }

    except Exception as e:
        builder_logger.error(f"Pipeline failed: {e}")
        # CHANGED: print() → builder_logger.error()

        return {
            "success":      False,
            "error":        str(e),
            "gaps":         [],
            "rewritten_ad": user_ad,
            "changes_made": "Analysis failed — please try again.",
            "word_count":   len(user_ad.split())
        }