import json
import os

PRODUCT_TO_CATEGORY = {
    "running shoes": "Sports & Fitness", "whey protein": "Sports & Fitness",
    "gym membership": "Sports & Fitness", "sports t-shirt": "Sports & Fitness",
    "wireless earbuds": "Electronics", "laptop": "Electronics",
    "smartphone": "Electronics", "lipstick": "Beauty & Personal Care",
    "sunscreen": "Beauty & Personal Care", "face wash": "Beauty & Personal Care",
    "sanitary pads": "Health & Hygiene", "ethnic wear": "Fashion",
    "backpack": "Fashion", "eyeglasses": "Fashion",
    "grocery delivery app": "Apps & Services", "e-commerce app": "Apps & Services",
    "food delivery app": "Apps & Services", "home services app": "Apps & Services",
    "online learning platform": "Education",
    "tea cafe": "Food & Beverage", "specialty coffee": "Food & Beverage",
}

def load_benchmarks():
    path = os.path.join("data", "benchmarks.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_category(product_desc):
    product_desc = product_desc.lower().strip()
    for product, category in PRODUCT_TO_CATEGORY.items():
        if product in product_desc:
            return category
    return "Other"

def calculate_percentile(user_score, all_scores_sorted):
    below = sum(1 for s in all_scores_sorted if s < user_score)
    return round(below / len(all_scores_sorted) * 100)

def get_market_position(percentile):
    if percentile >= 80: return "Top Performer"
    if percentile >= 60: return "Above Average"
    if percentile >= 40: return "Average"
    if percentile >= 20: return "Below Average"
    return "Needs Significant Work"

def generate_insight(user_score, industry_avg, dimension_gaps):
    if not dimension_gaps:
        return "Run analysis to see detailed insights."
    gap = user_score - industry_avg
    sorted_gaps = sorted(dimension_gaps, key=lambda x: x["gap"])
    weakest  = sorted_gaps[0]
    strongest = sorted_gaps[-1]
    if gap >= 0:
        insight = "You are {:.1f} pts above industry average. ".format(gap)
    else:
        insight = "You are {:.1f} pts below industry average. ".format(abs(gap))
    if strongest["gap"] > 0:
        insight += "Your {} is a strength (+{:.1f}). ".format(
            strongest["dimension"], strongest["gap"])
    insight += "Focus on {} first - biggest gap at {:.1f} pts.".format(
        weakest["dimension"], weakest["gap"])
    return insight

def calculate_benchmark(user_score, user_dimensions, product_desc):
    benchmarks = load_benchmarks()
    gb = benchmarks["global"]
    category = get_category(product_desc)
    cb = benchmarks["by_category"].get(category, None)

    industry_avg    = gb["avg_score"]
    top_score       = gb["top_score"]
    top_brand       = gb["top_brand"]
    top_platform    = gb["top_platform"]
    percentile      = calculate_percentile(user_score, gb["all_scores_sorted"])
    gap_to_avg      = round(user_score - industry_avg, 1)
    gap_to_top      = user_score - top_score
    cat_avg         = cb["avg_score"]   if cb else industry_avg
    cat_top         = cb["top_score"]   if cb else top_score
    cat_brand       = cb["top_brand"]   if cb else top_brand

    dim_gaps = []
    if user_dimensions:
        for dim in user_dimensions:
            dim_name = dim["dimension"]
            user_dim = dim["score"]
            ind_dim  = gb["avg_dimensions"].get(dim_name, 5)
            gap      = round(user_dim - ind_dim, 1)
            dim_gaps.append({
                "dimension":    dim_name,
                "user_score":   user_dim,
                "industry_avg": ind_dim,
                "gap":          gap,
            })

    dim_gaps_sorted = sorted(dim_gaps, key=lambda x: x["gap"])

    return {
        "user_score":          user_score,
        "industry_avg":        industry_avg,
        "category":            category,
        "category_avg":        cat_avg,
        "category_top_score":  cat_top,
        "category_top_brand":  cat_brand,
        "global_top_score":    top_score,
        "global_top_brand":    top_brand,
        "global_top_platform": top_platform,
        "percentile":          percentile,
        "gap_to_avg":          gap_to_avg,
        "gap_to_top":          gap_to_top,
        "market_position":     get_market_position(percentile),
        "dimension_gaps":      dim_gaps_sorted,
        "insight":             generate_insight(user_score, industry_avg, dim_gaps),
    }
