from fastapi import APIRouter, HTTPException
from api.schemas.strategies import (
    StrategiesRequest,
    StrategiesResponse,
    StrategyResult,
    DimensionComparison
)
from agents.strategy_builder import generate_all_strategies

router = APIRouter(prefix="/strategies", tags=["Strategies"])

@router.post("", response_model=StrategiesResponse)
async def generate_strategies(request: StrategiesRequest):
    """
    Generate 3 parallel ad strategies.
    Conversion, Emotional, Urgency — all in parallel.
    """
    try:
        gaps = [
            {
                "gap": g.gap,
                "severity": g.severity,
                "competitor_does": g.competitor_does
            }
            for g in request.gaps
        ]

        result = generate_all_strategies(
            original_ad=request.ad_copy,
            gaps=gaps
        )

        strategies = [
            StrategyResult(
                strategy_key  = s["strategy_key"],
                strategy_name = s["strategy_name"],
                strategy_icon = s["strategy_icon"],
                use_case      = s["use_case"],
                description   = s["description"],
                rewritten_ad  = s["rewritten_ad"],
                changes_made  = s["changes_made"],
                word_count    = s["word_count"],
                score         = s.get("score"),
                grade         = s.get("grade"),
                is_winner     = s.get("is_winner", False)
            )
            for s in result["strategies"]
        ]

        dim_comparison = [
            DimensionComparison(
                dimension  = dim,
                Conversion = scores.get("Conversion"),
                Emotional  = scores.get("Emotional"),
                Urgency    = scores.get("Urgency")
            )
            for dim, scores in result["dimension_comparison"].items()
        ]

        return StrategiesResponse(
            success              = True,
            strategies           = strategies,
            winner_key           = result.get("winner_key"),
            winner_score         = result.get("winner_score"),
            dimension_comparison = dim_comparison,
            recommendation       = result["recommendation"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Strategy generation failed: {}".format(str(e))
        )