"""
compute_benchmarks.py
Purpose: Pre-compute benchmark scores for all 50 competitor ads.
Run this ONCE — output saved to data/benchmarks.json
Usage: python data/compute_benchmarks.py
"""

import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.explainable_scorer import calculate_explainable_score

PRODUCT_TO_CATEGORY = {
    "running shoes":           "Sports & Fitness",
    "whey protein":            "Sports & Fitness",
    "gym membership":          "Sports & Fitness",
    "sports t-shirt":          "Sports & Fitness",
    "wireless earbuds":        "Electronics",
    "laptop":                  "Electronics",
    "smartphone":              "Electronics",
    "lipstick":                "Beauty & Personal Care",
    "sunscreen":               "Beauty & Personal Care",
    "face wash":               "Beauty & Personal Care",
    "sanitary pads":           "Health & Hygiene",
    "ethnic wear":             "Fashion",
    "backpack":                "Fashion",
    "eyeglasses":              "Fashion",
    "grocery delivery app":    "Apps & Services",
    "e-commerce app":          "Apps & Services",
    "food delivery app":       "Apps & Services",
    "home services app":       "Apps & Services",
    "online learning platform":"Education",
    "tea cafe":                "Food & Beverage",
    "specialty coffee":        "Food & Beverage",
}

def avg(lst):
    return round(sum(lst) / len(lst), 1) if lst else 0

def compute():
    with open("data/competitors.json", "r", encoding="utf-8-sig") as f:
        ads = json.load(f)

    print("Computing scores for {} ads...".format(len(ads)))
    print("This will take 3-5 minutes\n")

    scored_ads = []
    failed = []

    for i, ad in enumerate(ads):
        brand    = ad.get("brand", "Unknown")
        product  = ad.get("product", "")
        ad_copy  = ad.get("ad_copy", "")
        platform = ad.get("platform", "")
        category = PRODUCT_TO_CATEGORY.get(product, "Other")

        print("[{}/{}] Scoring: {} - {}".format(i+1, len(ads), brand, product))

        result = calculate_explainable_score(ad_copy)

        if result.get("error"):
            print("  FAILED: {}".format(result.get("error_msg")))
            failed.append(brand)
            continue

        scored_ads.append({
            "brand":       brand,
            "product":     product,
            "category":    category,
            "platform":    platform,
            "ad_copy":     ad_copy,
            "total_score": result["total_score"],
            "dimensions":  {d["dimension"]: d["score"] for d in result["dimensions"]}
        })

        time.sleep(1)

    print("\nScored: {} / {}".format(len(scored_ads), len(ads)))
    if failed:
        print("Failed:", failed)

    dim_names = [
        "Hook Strength", "Value Proposition", "Call to Action",
        "Emotional Trigger", "Clarity & Readability", "Length Optimization"
    ]

    all_scores = [a["total_score"] for a in scored_ads]
    all_scores_sorted = sorted(all_scores)

    global_dims = {}
    for dim in dim_names:
        scores = [a["dimensions"].get(dim, 5) for a in scored_ads]
        global_dims[dim] = avg(scores)

    bands = [0, 20, 40, 60, 80, 101]
    distribution = []
    for j in range(len(bands)-1):
        count = sum(1 for s in all_scores if bands[j] <= s < bands[j+1])
        distribution.append(round(count / len(all_scores) * 100, 1))

    top_ad = max(scored_ads, key=lambda x: x["total_score"])

    global_benchmark = {
        "total_ads":          len(scored_ads),
        "avg_score":          avg(all_scores),
        "min_score":          min(all_scores),
        "max_score":          max(all_scores),
        "top_brand":          top_ad["brand"],
        "top_score":          top_ad["total_score"],
        "top_platform":       top_ad["platform"],
        "top_category":       top_ad["category"],
        "avg_dimensions":     global_dims,
        "all_scores_sorted":  all_scores_sorted,
        "score_distribution": distribution
    }

    categories = {}
    for ad in scored_ads:
        cat = ad["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ad)

    category_benchmark = {}
    for cat, cat_ads in categories.items():
        cat_scores = [a["total_score"] for a in cat_ads]
        cat_top = max(cat_ads, key=lambda x: x["total_score"])
        cat_dims = {}
        for dim in dim_names:
            scores = [a["dimensions"].get(dim, 5) for a in cat_ads]
            cat_dims[dim] = avg(scores)
        category_benchmark[cat] = {
            "count":          len(cat_ads),
            "avg_score":      avg(cat_scores),
            "min_score":      min(cat_scores),
            "max_score":      max(cat_scores),
            "top_brand":      cat_top["brand"],
            "top_score":      cat_top["total_score"],
            "top_platform":   cat_top["platform"],
            "avg_dimensions": cat_dims,
            "brands":         [a["brand"] for a in cat_ads]
        }

    benchmark_data = {
        "computed_at":         "2026-06-09",
        "global":              global_benchmark,
        "by_category":         category_benchmark,
        "product_to_category": PRODUCT_TO_CATEGORY
    }

    with open("data/benchmarks.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    print("\nSaved to data/benchmarks.json")
    print("Global avg: {}".format(global_benchmark["avg_score"]))
    print("Top scorer: {} - {}".format(top_ad["brand"], top_ad["total_score"]))

if __name__ == "__main__":
    compute()
