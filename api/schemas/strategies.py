from pydantic import BaseModel
from typing import Optional

class GapInput(BaseModel):
    gap: str
    severity: str
    competitor_does: str

class StrategiesRequest(BaseModel):
    analysis_id: Optional[str] = None
    # /analyze se mila id — taaki yeh strategies us analysis se link ho
    ad_copy: str
    gaps: list[GapInput]
    product_description: str

class StrategyResult(BaseModel):
    strategy_key: str
    strategy_name: str
    strategy_icon: str
    use_case: str
    description: str
    rewritten_ad: str
    changes_made: str
    word_count: int
    score: Optional[int] = None
    grade: Optional[str] = None
    is_winner: bool = False

class DimensionComparison(BaseModel):
    dimension: str
    Conversion: Optional[int] = None
    Emotional: Optional[int] = None
    Urgency: Optional[int] = None

class StrategiesResponse(BaseModel):
    success: bool
    strategies: list[StrategyResult]
    winner_key: Optional[str] = None
    winner_score: Optional[int] = None
    dimension_comparison: list[DimensionComparison]
    recommendation: str
    error_message: Optional[str] = None