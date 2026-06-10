# api/routers/analyze.py
# Purpose: POST /analyze endpoint
#
# WHY THIS FILE EXISTS:
# Ye file "waiter" hai — request leta hai,
# existing services ko call karta hai,
# response assemble karke return karta hai.
# Business logic ZERO — sirf orchestration.

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from api.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    GapItem,
    DimensionResult,
    TopFix,
    ExplainableScoreResult,
    CompetitorAd
)

# ── Existing services — UNCHANGED ──
from rag.retriever              import get_similar_ads
from agents.analyst             import analyze_gaps
from agents.builder             import rewrite_ad
from scoring.explainable_scorer import calculate_explainable_score

# APIRouter — ek mini app jaise
# prefix="/analyze" — har route /analyze se shuru hoga
router = APIRouter(prefix="/analyze", tags=["Analysis"])
# tags=["Analysis"] — Swagger UI mein grouping ke liye


# ============================================================
# POST /analyze — main endpoint
# ============================================================

@router.post("", response_model=AnalyzeResponse)
# "" — kyunki prefix already "/analyze" hai
# response_model — FastAPI automatically validate karega response
async def analyze_ad(request: AnalyzeRequest):
    """
    Main AdCopilot pipeline:
    1. RAG — find similar competitor ads
    2. PARALLEL — score + identify gaps
    3. Rewrite ad
    4. Return complete analysis
    """

    start_time = time.time()
    # start_time — processing time calculate karne ke liye

    try:
        # ── STEP 1: RAG ──
        # Competitor ads dhundho — existing function, unchanged
        similar_ads_raw = get_similar_ads(
            request.product_description,
            n_results=5
        )

        # Raw result ko schema mein convert karo
        competitor_ads = [
            CompetitorAd(
                ad_copy          = ad.get("ad_copy", ""),
                brand            = ad.get("brand", "Unknown"),
                similarity_score = ad.get("similarity_score", 0.0),
                platform         = ad.get("platform", "")
            )
            for ad in similar_ads_raw
        ]

        # ── STEP 2: PARALLEL — scorer + analyst ──
        # ThreadPoolExecutor — dono saath chalao
        # Exactly same approach jo app.py mein tha
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_expl = executor.submit(
                calculate_explainable_score,
                request.ad_copy
                # explainable scorer — 6 dimensions
            )
            future_gaps = executor.submit(
                analyze_gaps,
                request.ad_copy,
                request.product_description
                # analyst agent — gap identification
            )

            expl_raw = future_expl.result()
            gaps_raw = future_gaps.result()
            # .result() — wait karo jab tak complete na ho

        # ── STEP 3: Validate scorer output ──
        if expl_raw.get("error"):
            raise HTTPException(
                status_code=422,
                detail="Scoring failed: {}".format(
                    expl_raw.get("error_msg", "Unknown error")
                )
            )
            # HTTPException — FastAPI ka standard error response
            # 422 = Unprocessable Entity

        # ── STEP 4: Rewrite ad ──
        rewrite_raw = rewrite_ad(
            original_ad = request.ad_copy,
            gaps        = gaps_raw
        )

        # ── STEP 5: Assemble response ──

        # Gaps list convert karo
        gaps = [
            GapItem(
                gap             = g.get("gap", ""),
                severity        = g.get("severity", "medium"),
                competitor_does = g.get("competitor_does", "")
            )
            for g in gaps_raw
            if isinstance(g, dict)
        ]

        # Dimensions convert karo
        dimensions = [
            DimensionResult(
                dimension  = d["dimension"],
                score      = d["score"],
                weight     = d["weight"],
                weighted   = d["weighted"],
                rating     = d["rating"],
                reason     = d["reason"],
                evidence   = d["evidence"],
                suggestion = d["suggestion"]
            )
            for d in expl_raw.get("dimensions", [])
        ]

        # Top fixes convert karo
        top_3_fixes = [
            TopFix(
                priority  = f["priority"],
                dimension = f["dimension"],
                action    = f["action"],
                impact    = f["impact"]
            )
            for f in expl_raw.get("top_3_fixes", [])
        ]

        # ExplainableScoreResult assemble karo
        explainable_score = ExplainableScoreResult(
            total_score = expl_raw["total_score"],
            grade       = expl_raw["grade"],
            one_liner   = expl_raw["one_liner"],
            word_count  = expl_raw["word_count"],
            dimensions  = dimensions,
            top_3_fixes = top_3_fixes
        )

        processing_time = round(time.time() - start_time, 2)
        # Kitne seconds lage — useful for performance monitoring

        # ── STEP 6: Return response ──
        return AnalyzeResponse(
            success             = True,
            processing_time     = processing_time,
            ad_copy             = request.ad_copy,
            product_description = request.product_description,
            gaps                = gaps,
            rewritten_ad        = rewrite_raw["rewritten_ad"],
            changes_made        = rewrite_raw["changes_made"],
            word_count          = rewrite_raw["word_count"],
            explainable_score   = explainable_score,
            competitor_ads      = competitor_ads
        )

    except HTTPException:
        raise
        # HTTPException ko re-raise karo — already formatted hai

    except Exception as e:
        # Unexpected error — 500 Internal Server Error
        raise HTTPException(
            status_code=500,
            detail="Analysis failed: {}".format(str(e))
        )
