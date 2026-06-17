# api/schemas/benchmark.py
# Purpose: Pydantic models for /benchmark endpoint

from pydantic import BaseModel
from typing import Optional


class DimensionInput(BaseModel):
    # Ek dimension — analyze endpoint se aata hai
    dimension: str
    score:     int


class BenchmarkRequest(BaseModel):
    user_score:          int
    dimensions:          list[DimensionInput]
    product_description: str


class DimensionGap(BaseModel):
    dimension:    str
    user_score:   int
    industry_avg: float
    gap:          float


class BenchmarkResponse(BaseModel):
    success:               bool
    user_score:            int
    industry_avg:          float
    category:              str
    category_avg:          float
    category_top_score:    int
    category_top_brand:    str
    global_top_score:      int
    global_top_brand:      str
    global_top_platform:   str
    percentile:            int
    gap_to_avg:            float
    gap_to_top:            int
    market_position:       str
    dimension_gaps:        list[DimensionGap]
    insight:               str
    error_message:         Optional[str] = None
