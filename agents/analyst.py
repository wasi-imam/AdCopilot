# analyst.py
# Purpose: Agent 1 — Compare user's ad against competitor ads
# and identify specific gaps as structured JSON.
#
# WHAT CHANGED FROM ORIGINAL:
# 1. RAG call try-except mein — ChromaDB fail ho toh empty list
# 2. Retry logic added — same as scorer
# 3. Safe JSON parsing — same helper logic
# 4. Graceful degradation — RAG bina bhi kaam karta hai
# 5. Fallback gaps — LLM fail ho toh bhi kuch return hoga
# 6. Input validation — empty inputs reject

import os
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Constants — same pattern as scorer
MAX_RETRIES  = 3
RETRY_DELAY  = 2


# ============================================================
# NEW FUNCTION: Safe RAG retrieval
# WHAT: get_similar_ads ko try-except mein wrap kiya
# WHERE: analyze_gaps ke shuruwat mein call hoti hai
# WHY: Pehle ChromaDB error = poora analyst crash
#      Ab ChromaDB error = empty list, analyst continues
# ============================================================
def _safe_get_similar_ads(product_description: str) -> list:
    """
    Safely retrieve similar ads from ChromaDB.
    Returns empty list if ChromaDB is unavailable.
    App continues even without RAG context.
    """
    try:
        from rag.retriever import get_similar_ads, format_for_agent
        similar_ads = get_similar_ads(product_description, n_results=5)
        context     = format_for_agent(similar_ads)
        return similar_ads, context
        # Dono return karo — list aur formatted text

    except Exception as e:
        # ChromaDB nahi mili, ya embedder nahi chala
        # Koi bhi error — gracefully handle karo
        print(f"RAG retrieval failed: {e}")
        print("Continuing without competitor context...")
        return [], "No competitor context available — analyzing ad independently."
        # Empty list + fallback message
        # Analyst ab bhi chalega — sirf competitor data nahi hoga


# ============================================================
# NEW FUNCTION: Safe JSON parser — same as scorer mein tha
# WHAT: LLM ka dirty JSON output clean karke parse karo
# WHERE: analyze_gaps mein LLM response ke baad call hoti hai
# WHY: LLM kabhi kabhi markdown ya extra text add karta hai
# ============================================================
def _parse_gaps_json(raw_output: str) -> list:
    """
    Safely parse LLM JSON array output.
    Handles markdown, extra text, malformed JSON.
    """
    cleaned = raw_output.strip()

    # Remove markdown code blocks
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                # Array chahiye — [ se shuru hona chahiye
                cleaned = part
                break

    # Find JSON array boundaries
    start = cleaned.find("[")
    end   = cleaned.rfind("]") + 1
    # rfind — aakhri ] dhundo
    # Array ke liye [ aur ] chahiye — object ke liye { } tha

    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    return json.loads(cleaned)


# ============================================================
# NEW: Fallback gaps generator
# WHAT: Jab LLM completely fail ho — generic gaps return karo
# WHERE: analyze_gaps mein — sab retries fail hone ke baad
# WHY: Pehle sab fail hone pe crash — ab partial result milta hai
# ============================================================
def _get_fallback_gaps() -> list:
    """
    Return generic gaps when LLM analysis fails completely.
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
            "competitor_does": "Most successful ads end with Shop Now, Order Today, or similar CTA"
        },
        {
            "gap":             "Ensure your hook (first line) is compelling",
            "severity":        "high",
            "competitor_does": "Top performing ads open with a bold statement or question"
        }
    ]
    # Generic but useful advice
    # User gets actionable feedback even when LLM fails


# ============================================================
# UPGRADED FUNCTION: Main gap analysis
# WHAT CHANGED: RAG wrapped in try-except, retry loop added,
#               fallback gaps added, validation added
# WHERE: Full function rewritten with error handling
# WHY: Original crashed on any single failure point
# ============================================================
def analyze_gaps(user_ad: str, product_description: str) -> list:
    """
    Compare user's ad against competitor ads.
    Returns list of gap dictionaries.
    Now handles RAG failures and LLM failures gracefully.
    """

    # NEW: Basic input check — pehle nahi tha
    if not user_ad or not user_ad.strip():
        return _get_fallback_gaps()

    if not product_description or not product_description.strip():
        product_description = "general product"
        # Empty description — generic use karo
        # Crash mat karo — best effort karo

    # NEW: Safe RAG call — pehle direct call tha, no protection
    similar_ads, competitor_context = _safe_get_similar_ads(product_description)

    # RAG ka status note karo — prompt mein use hoga
    rag_available = len(similar_ads) > 0
    # True  — ChromaDB se data mila
    # False — RAG fail hua, bina context ke chalenge

    # ============================================================
    # Build prompt — RAG available hai ya nahi uske hisaab se
    # WHAT CHANGED: Conditional prompt — pehle sirf ek prompt tha
    # WHY: RAG data nahi hai toh LLM ko alag instructions do
    # ============================================================
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
        # NEW: Fallback prompt — RAG nahi hai toh general analysis
        # Pehle yeh nahi tha — RAG fail = crash
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

    # NEW: Retry loop — same pattern as scorer
    # WHAT CHANGED: try-except + retry added around API call
    # WHY: Pehle ek failure = crash, ab 3 chances
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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
                temperature=0.2,
                max_tokens=600
            )

            raw_output = response.choices[0].message.content.strip()

            # NEW: Safe JSON parsing — pehle direct json.loads() tha
            gaps = _parse_gaps_json(raw_output)

            # NEW: Validate each gap object — pehle nahi tha
            validated_gaps = []
            for gap in gaps:
                if not isinstance(gap, dict):
                    continue
                    # Dict nahi hai — skip karo

                if not all(key in gap for key in ["gap", "severity", "competitor_does"]):
                    continue
                    # Koi key missing — skip karo

                # Normalize severity
                gap["severity"] = str(gap.get("severity", "medium")).lower().strip()
                if gap["severity"] not in ["high", "medium", "low"]:
                    gap["severity"] = "medium"

                validated_gaps.append(gap)

            if not validated_gaps:
                # Parsing hua but koi valid gap nahi mila
                raise ValueError("No valid gaps in LLM response")

            return validated_gaps
            # Sab sahi — return karo

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            print(f"Attempt {attempt + 1} failed (JSON): {last_error}")

        except ValueError as e:
            last_error = f"Validation error: {e}"
            print(f"Attempt {attempt + 1} failed (validation): {last_error}")

        except Exception as e:
            last_error = f"API error: {e}"
            print(f"Attempt {attempt + 1} failed (API): {last_error}")

        if attempt < MAX_RETRIES - 1:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

    # NEW: Fallback — pehle nahi tha
    # Sab retries fail — generic gaps return karo
    print(f"All {MAX_RETRIES} attempts failed. Using fallback gaps.")
    return _get_fallback_gaps()


# ============================================================
# format_gaps_for_display — SAME AS BEFORE, no change
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