# scorer.py
# Purpose: Calculate a viral score (0-100) for any ad copy.
#
# WHAT CHANGED FROM ORIGINAL:
# 1. Added retry logic    — Groq API rate limit pe auto retry karta hai
# 2. Added error handling — har API call try-except mein hai
# 3. Added fallback score — agar LLM fail ho toh bhi score milega
# 4. Added JSON cleaning  — LLM ka dirty output handle karta hai
# 5. Added input validation — empty ya too-long input reject karta hai

import os
import json
import time
# time — NEW: retry logic mein delay ke liye
# time.sleep(2) = 2 second ruko

from groq import Groq
from pydantic import BaseModel, ValidationError
# ValidationError — NEW: import kiya
# Pydantic ka error — jab LLM wrong types de
# Pehle sirf BaseModel import tha

from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ============================================================
# NEW: Constants — pehle yeh nahi tha
# Sab magic numbers ek jagah — easy to change
# ============================================================
MAX_RETRIES     = 3
# Kitni baar retry karein agar API fail ho
# 3 chances dete hain — phir give up

RETRY_DELAY     = 2
# Retry ke beech kitne seconds wait karein
# 2 second — API ko recover karne ka time

MAX_AD_LENGTH   = 200
# Maximum words allowed in ad copy
# 200 se zyada = likely not an ad — reject karo

MIN_AD_LENGTH   = 3
# Minimum words
# 3 se kam = too short to analyze

# ============================================================
# Pydantic Model — SAME AS BEFORE, no change
# ============================================================
class AdMetrics(BaseModel):
    hook_strength:       int
    sentiment_stability: int
    keyword_density:     int
    clarity:             int


# ============================================================
# NEW FUNCTION: Input validator
# Pehle yeh nahi tha — directly LLM call hota tha
# ============================================================
def validate_ad_input(ad_copy: str) -> tuple:
    """
    Validate ad copy before sending to LLM.
    Returns: (is_valid: bool, error_message: str)

    WHY: Pehle koi validation nahi tha — empty string bhi
    LLM ko bhej dete the — waste of tokens + crash risk.
    """
    if not ad_copy or not ad_copy.strip():
        # not ad_copy     — None ya empty string check
        # not .strip()    — sirf spaces wala string bhi reject
        return False, "Ad copy cannot be empty."

    word_count = len(ad_copy.strip().split())

    if word_count < MIN_AD_LENGTH:
        return False, f"Ad copy too short — minimum {MIN_AD_LENGTH} words required."

    if word_count > MAX_AD_LENGTH:
        return False, f"Ad copy too long — maximum {MAX_AD_LENGTH} words allowed. Your ad has {word_count} words."

    return True, ""
    # True = valid, empty string = no error message


# ============================================================
# NEW FUNCTION: Safe JSON parser
# Pehle directly json.loads() call karte the — crash risk
# ============================================================
def _parse_llm_json(raw_output: str) -> dict:
    """
    Safely parse LLM JSON output.
    Handles markdown backticks, extra text, malformed JSON.

    WHY: LLM kabhi kabhi yeh return karta hai:
```json
    {"hook_strength": 8}
```
    Pehle yeh crash karta tha — ab handle karta hai.
    """
    # Step 1: Strip whitespace
    cleaned = raw_output.strip()

    # Step 2: Remove markdown code blocks
    # LLM kabhi kabhi ```json ... ``` wrap karta hai
    if "```" in cleaned:
        parts = cleaned.split("```")
        # Example: ["some text", "json\n{...}", ""]
        # parts[1] mein actual content hoga
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
                # "json\n{...}" se "json" hata do
            if part.startswith("{"):
                cleaned = part
                break
                # Pehla valid JSON object mila — use karo

    # Step 3: Find JSON object boundaries
    # Kabhi kabhi LLM extra text add karta hai before/after JSON
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    # .find("{")  — pehla { kahan hai
    # .rfind("}") — aakhri } kahan hai
    # +1          — slice mein end include karne ke liye

    if start != -1 and end > start:
        # -1 matlab nahi mila
        # end > start matlab valid range hai
        cleaned = cleaned[start:end]

    return json.loads(cleaned)
    # Ab clean JSON parse karo


# ============================================================
# UPGRADED FUNCTION: LLM metric extraction with retry
# WHAT CHANGED: try-except + retry loop + fallback added
# WHERE: extract_metrics_from_llm function
# WHY: Pehle ek bhi failure pe crash — ab 3 chances
# ============================================================
def extract_metrics_from_llm(ad_copy: str) -> AdMetrics:
    """
    Send ad copy to LLM and extract structured metrics.
    Now includes retry logic and fallback values.
    """

    prompt = f"""You are an expert marketing analyst. Analyze the following ad copy and return a JSON object with exactly these 4 keys:

- hook_strength (integer 1-10): How compelling is the opening line?
- sentiment_stability (integer 1-10): Is the emotional tone consistent?
- keyword_density (integer 1-10): Are relevant keywords naturally included?
- clarity (integer 1-10): Is the core message immediately clear?

Ad Copy: "{ad_copy}"

Return ONLY valid JSON. No explanation. No markdown.
Example: {{"hook_strength": 8, "sentiment_stability": 7, "keyword_density": 6, "clarity": 9}}"""

    # NEW: Retry loop — pehle yeh nahi tha
    # Pehle: seedha API call — fail = crash
    # Now:   3 chances — fail = wait 2s — retry
    last_error = None
    # last_error — loop ke baad bata sake ki aakhri error kya thi

    for attempt in range(MAX_RETRIES):
        # range(3) = 0, 1, 2 — teen attempts
        try:
            # try block — yahan jo bhi error aaye — crash nahi hoga
            # except block mein catch hoga

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150
            )

            raw_output = response.choices[0].message.content.strip()

            # NEW: Safe JSON parsing — pehle directly json.loads() tha
            parsed = _parse_llm_json(raw_output)

            # NEW: Pydantic validation with error handling
            metrics = AdMetrics(**parsed)
            # Agar LLM ne string diya instead of int —
            # Pydantic ValidationError throw karega
            # try-except catch karega — crash nahi hoga

            return metrics
            # Sab sahi — return karo
            # Loop yahan khatam — aage nahi jayega

        except ValidationError as e:
            # Pydantic error — wrong types
            last_error = f"Invalid metric types from LLM: {e}"
            print(f"Attempt {attempt + 1} failed (validation): {last_error}")

        except json.JSONDecodeError as e:
            # JSON parse error — malformed response
            last_error = f"LLM returned invalid JSON: {e}"
            print(f"Attempt {attempt + 1} failed (JSON): {last_error}")

        except Exception as e:
            # Koi bhi aur error — network, API down, etc.
            last_error = f"API call failed: {e}"
            print(f"Attempt {attempt + 1} failed (API): {last_error}")

        # NEW: Retry delay — pehle nahi tha
        if attempt < MAX_RETRIES - 1:
            # Last attempt ke baad wait mat karo
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            # time.sleep() — program ko X seconds ke liye rokta hai

    # NEW: Fallback — pehle nahi tha
    # Sab attempts fail — default values return karo
    # App crash nahi hoga — user ko partial result milega
    print(f"All {MAX_RETRIES} attempts failed. Using fallback metrics.")
    print(f"Last error: {last_error}")

    return AdMetrics(
        hook_strength=5,
        sentiment_stability=5,
        keyword_density=5,
        clarity=5
        # 5/10 = neutral score — nahi jaante actual value
        # Score pe note lagana chahiye — UI mein batana
    )


# ============================================================
# UPGRADED FUNCTION: Length score — SAME LOGIC, no change
# ============================================================
def calculate_length_score(ad_copy: str) -> int:
    """
    Calculate length penalty score.
    Sweet spot: 15 to 50 words.
    """
    word_count = len(ad_copy.split())

    if 15 <= word_count <= 50:
        return 10
    elif word_count < 15:
        return max(1, word_count - 5)
    else:
        penalty = (word_count - 50) // 5
        return max(1, 10 - penalty)


# ============================================================
# UPGRADED FUNCTION: Main scoring function
# WHAT CHANGED: input validation added at the top
# WHERE: calculate_viral_score function — starting mein
# WHY: Pehle invalid input directly LLM tak pahunchta tha
# ============================================================
def calculate_viral_score(ad_copy: str) -> dict:
    """
    Main function — calculate complete viral score.
    Now validates input before processing.
    """

    # NEW: Validate input first — pehle yeh nahi tha
    is_valid, error_msg = validate_ad_input(ad_copy)
    if not is_valid:
        # Invalid input — meaningful error return karo
        # Crash nahi — dictionary return karo with error flag
        return {
            "error":       True,
            "error_msg":   error_msg,
            "total_score": 0,
            "grade":       "N/A",
            "word_count":  len(ad_copy.split()) if ad_copy else 0,
            "breakdown":   {
                "length_score":        0,
                "hook_strength":       0,
                "sentiment_stability": 0,
                "keyword_density":     0,
                "clarity":             0
            }
        }

    # Normal flow — same as before
    word_count   = len(ad_copy.split())
    length_score = calculate_length_score(ad_copy)
    metrics      = extract_metrics_from_llm(ad_copy)

    W_length    = 0.15
    W_hook      = 0.30
    W_sentiment = 0.20
    W_keywords  = 0.20
    W_clarity   = 0.15

    raw_score = (
        W_length    * (length_score               * 10) +
        W_hook      * (metrics.hook_strength      * 10) +
        W_sentiment * (metrics.sentiment_stability * 10) +
        W_keywords  * (metrics.keyword_density    * 10) +
        W_clarity   * (metrics.clarity            * 10)
    )

    final_score = round(raw_score)

    # NEW: error flag False — sab sahi tha
    return {
        "error":       False,
        # NEW field — app.py check karega yeh flag
        # False = sab theek, True = kuch problem thi

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
            "length":    W_length,
            "hook":      W_hook,
            "sentiment": W_sentiment,
            "keywords":  W_keywords,
            "clarity":   W_clarity
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