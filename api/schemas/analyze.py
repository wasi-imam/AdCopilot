# api/schemas/analyze.py
# Purpose: Pydantic models for /analyze endpoint
#
# WHY THIS FILE EXISTS:
# FastAPI ko batana padta hai — request mein kya aayega
# aur response mein kya jaayega.
# Pydantic automatically validate karta hai —
# agar required field missing ho toh auto error.

from pydantic import BaseModel, validator
from typing import Optional


# ============================================================
# REQUEST SCHEMA — frontend se kya aayega
# ============================================================

class AnalyzeRequest(BaseModel):
    ad_copy: str
    # User ka original ad — required field
    # str = string hona chahiye

    product_description: str
    # Product description — required field

    @validator("ad_copy")
    def validate_ad_copy(cls, v):
        # v = value jo aaya request mein
        if not v or not v.strip():
            raise ValueError("Ad copy cannot be empty")
        words = len(v.strip().split())
        if words < 3:
            raise ValueError("Ad copy too short — minimum 3 words")
        if words > 200:
            raise ValueError("Ad copy too long — maximum 200 words")
        return v.strip()
        # .strip() — extra spaces remove karo

    @validator("product_description")
    def validate_product_desc(cls, v):
        if not v or not v.strip():
            raise ValueError("Product description cannot be empty")
        return v.strip()


# ============================================================
# RESPONSE SCHEMAS — API se kya jaayega
# ============================================================

class GapItem(BaseModel):
    # Ek gap — analyst agent se aata hai
    gap:             str   # gap description
    severity:        str   # "high", "medium", "low"
    competitor_does: str   # what competitors do instead

class DimensionResult(BaseModel):
    # Ek dimension ka score — explainable scorer se
    dimension:  str    # "Hook Strength"
    score:      int    # 1-10
    weight:     float  # 0.25
    weighted:   float  # contribution to total
    rating:     str    # "Poor", "Average", "Good", "Excellent"
    reason:     str    # WHY this score
    evidence:   str    # exact text from ad
    suggestion: str    # HOW to improve

class TopFix(BaseModel):
    # Priority fix — top 3 improvements
    priority:  int    # 1, 2, 3
    dimension: str    # which dimension to fix
    action:    str    # what to do
    impact:    str    # expected point gain

class ExplainableScoreResult(BaseModel):
    # Complete explainable score output
    total_score: int
    grade:       str
    one_liner:   str
    word_count:  int
    dimensions:  list[DimensionResult]
    top_3_fixes: list[TopFix]

class CompetitorAd(BaseModel):
    # One competitor ad from RAG
    ad_copy:          str
    brand:            str
    similarity_score: float
    platform:         str

class AnalyzeResponse(BaseModel):
    # Complete response — sab kuch ek jagah
    success:             bool
    analysis_id:         Optional[str] = None
    # Supabase mein insert hone ke baad mila id — taaki frontend
    # ise baad mein /benchmark ya /strategies call mein use kar sake
    processing_time:     float   # seconds mein

    # Input echo — debugging ke liye useful
    ad_copy:             str
    product_description: str

    # Pipeline results
    gaps:                list[GapItem]
    rewritten_ad:        str
    changes_made:        str
    word_count:          int

    # Explainable score
    explainable_score:   ExplainableScoreResult

    # RAG results
    competitor_ads:      list[CompetitorAd]

    # Error — sirf tab jab success=False
    error_message:       Optional[str] = None
