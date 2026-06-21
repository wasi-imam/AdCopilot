# api/routers/benchmark.py
# Purpose: POST /benchmark endpoint
#
# WHY THIS FILE EXISTS:
# User ka score industry average se compare karta hai.
# benchmark_engine.py already exist karta hai — unchanged.
# Ye sirf HTTP layer hai.

from fastapi import APIRouter, HTTPException

from api.schemas.benchmark import (
    BenchmarkRequest,
    BenchmarkResponse,
    DimensionGap
)
from scoring.benchmark_engine import calculate_benchmark
from api.database import supabase

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


@router.post("", response_model=BenchmarkResponse)
async def benchmark_ad(request: BenchmarkRequest):
    """
    Compare user ad score against industry benchmarks.
    Uses pre-computed benchmarks from 50 competitor ads.
    """
    try:
        # Convert DimensionInput list to format benchmark_engine expects
        dimensions = [
            {"dimension": d.dimension, "score": d.score}
            for d in request.dimensions
        ]

        # Call existing benchmark engine — unchanged
        result = calculate_benchmark(
            user_score      = request.user_score,
            user_dimensions = dimensions,
            product_desc    = request.product_description
        )

        # Dimension gaps convert karo
        dimension_gaps = [
            DimensionGap(
                dimension    = dg["dimension"],
                user_score   = dg["user_score"],
                industry_avg = dg["industry_avg"],
                gap          = dg["gap"]
            )
            for dg in result.get("dimension_gaps", [])
        ]

        # ── Save to Supabase (best-effort) ──
        # Agar yeh fail ho jaye, user ko response phir bhi milna chahiye.
        try:
            supabase.table("benchmark_results").insert({
                "analysis_id":     request.analysis_id,
                "percentile":      result["percentile"],
                "industry_avg":    result["industry_avg"],
                "category":        result["category"],
                "category_avg":    result["category_avg"],
                "market_position": result["market_position"],
                "gap_to_avg":      result["gap_to_avg"],
                "gap_to_top":      result["gap_to_top"],
                "insight":         result["insight"],
            }).execute()
        except Exception as db_error:
            print(f"⚠️  Supabase insert failed: {db_error}")


        return BenchmarkResponse(
            success              = True,
            user_score           = result["user_score"],
            industry_avg         = result["industry_avg"],
            category             = result["category"],
            category_avg         = result["category_avg"],
            category_top_score   = result["category_top_score"],
            category_top_brand   = result["category_top_brand"],
            global_top_score     = result["global_top_score"],
            global_top_brand     = result["global_top_brand"],
            global_top_platform  = result["global_top_platform"],
            percentile           = result["percentile"],
            gap_to_avg           = result["gap_to_avg"],
            gap_to_top           = result["gap_to_top"],
            market_position      = result["market_position"],
            dimension_gaps       = dimension_gaps,
            insight              = result["insight"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Benchmark failed: {}".format(str(e))
        )
