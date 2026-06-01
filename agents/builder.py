# builder.py
# Purpose: Agent 2 — Rewrite ad copy based on analyst gaps.
#
# WHAT CHANGED FROM ORIGINAL:
# 1. Retry logic added — same pattern as scorer and analyst
# 2. Response parsing made safer — handles malformed output
# 3. Fallback result — LLM fail ho toh original ad return karo
# 4. Input validation — empty gaps handle karo

import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MAX_RETRIES = 3
RETRY_DELAY = 2


# ============================================================
# UPGRADED FUNCTION: rewrite_ad
# WHAT CHANGED: try-except + retry + fallback added
# WHERE: Entire function wrapped in retry loop
# WHY: Pehle LLM fail = crash, ab 3 chances + fallback
# ============================================================
def rewrite_ad(original_ad: str, gaps: list) -> dict:
    """
    Rewrite ad copy to fix identified gaps.
    Now handles LLM failures gracefully.
    """

    # Edge case — no gaps found
    if not gaps:
        return {
            "rewritten_ad": original_ad,
            "changes_made": "No gaps identified — original ad returned unchanged.",
            "word_count":   len(original_ad.split())
        }

    # Format gap instructions — same as before
    gap_instructions = ""
    for i, gap in enumerate(gaps, 1):
        # NEW: .get() use kiya — pehle direct access tha
        # .get() safe hai — key missing ho toh crash nahi
        severity = gap.get("severity", "medium").upper()
        gap_text = gap.get("gap", "Improve the ad")
        reference = gap.get("competitor_does", "Follow best practices")

        gap_instructions += f"{i}. [{severity}] Fix: {gap_text}\n"
        gap_instructions += f"   Reference: {reference}\n\n"

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

    # NEW: Retry loop — pehle nahi tha
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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
                temperature=0.7,
                max_tokens=500
            )

            raw_output = response.choices[0].message.content.strip()

            # NEW: Safer response parsing
            # WHAT CHANGED: Multiple separator checks added
            # WHY: LLM kabhi "---" nahi deta — pehle crash
            if "---" in raw_output:
                parts        = raw_output.split("---", 1)
                rewritten_ad = parts[0].strip()
                changes_raw  = parts[1].strip()

                if "CHANGES:" in changes_raw:
                    changes_text = changes_raw.replace("CHANGES:", "").strip()
                else:
                    changes_text = changes_raw

            else:
                # NEW: Separator nahi mila — poora output ad maano
                # Pehle yahan crash hota tha
                rewritten_ad = raw_output
                changes_text = "Ad rewritten to address identified gaps."

            # NEW: Basic validation — rewritten ad empty nahi hona chahiye
            if not rewritten_ad.strip():
                raise ValueError("Builder returned empty ad copy")

            return {
                "rewritten_ad": rewritten_ad,
                "changes_made": changes_text,
                "word_count":   len(rewritten_ad.split())
            }

        except ValueError as e:
            last_error = f"Validation: {e}"
            print(f"Attempt {attempt + 1} failed: {last_error}")

        except Exception as e:
            last_error = f"API error: {e}"
            print(f"Attempt {attempt + 1} failed: {last_error}")

        if attempt < MAX_RETRIES - 1:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

    # NEW: Fallback — pehle nahi tha
    # Sab fail — original ad return karo with error note
    print(f"Builder failed after {MAX_RETRIES} attempts. Returning original.")
    return {
        "rewritten_ad": original_ad,
        "changes_made": f"Rewrite service temporarily unavailable. Original ad returned.\nError: {last_error}",
        "word_count":   len(original_ad.split())
    }


# ============================================================
# UPGRADED FUNCTION: run_full_pipeline
# WHAT CHANGED: try-except wrapper added around full pipeline
# WHERE: Entire pipeline wrapped
# WHY: Agar kuch bhi fail ho — app.py ko clean error mile
# ============================================================
def run_full_pipeline(user_ad: str, product_description: str) -> dict:
    """
    Run complete 2-agent pipeline: Analyst → Builder.
    Now returns error info instead of crashing.
    """
    from agents.analyst import analyze_gaps

    try:
        print("Agent 1 (Analyst) running...")
        gaps = analyze_gaps(user_ad, product_description)
        print(f"Gaps identified: {len(gaps)}")

        print("Agent 2 (Builder) running...")
        result = rewrite_ad(original_ad=user_ad, gaps=gaps)
        print("Rewrite complete.")

        return {
            "success":      True,
            # NEW: success flag — app.py check karega
            "gaps":         gaps,
            "rewritten_ad": result["rewritten_ad"],
            "changes_made": result["changes_made"],
            "word_count":   result["word_count"]
        }

    except Exception as e:
        # NEW: Complete pipeline failure — pehle nahi tha
        print(f"Pipeline failed: {e}")
        return {
            "success":      False,
            "error":        str(e),
            "gaps":         [],
            "rewritten_ad": user_ad,
            "changes_made": "Analysis failed — please try again.",
            "word_count":   len(user_ad.split())
        }