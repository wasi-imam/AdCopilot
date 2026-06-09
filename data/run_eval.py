"""
run_eval.py
Purpose: Evaluate AdCopilot — does it actually improve ad quality?
Usage:   python data/run_eval.py
Output:  data/eval_results.json + terminal report
"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.explainable_scorer import calculate_explainable_score
from scoring.benchmark_engine   import calculate_benchmark
from agents.builder             import run_full_pipeline


def calculate_gap_fix_rate(before_dims, after_dims, gaps):
    """
    Check how many analyst-identified gaps were fixed.
    A gap is fixed if after_score > before_score for that dimension.
    """
    if not gaps:
        return 0.0

    fixed = 0
    for gap in gaps:
        gap_text = gap.get("gap", "").lower()
        for dim in before_dims:
            dim_name = dim["dimension"].lower()
            if any(word in gap_text for word in dim_name.split()):
                before_s = dim["score"]
                after_s  = next(
                    (d["score"] for d in after_dims if d["dimension"] == dim["dimension"]),
                    before_s
                )
                if after_s > before_s:
                    fixed += 1
                break

    return round(fixed / len(gaps) * 100, 1)


def run_evaluation():
    print("=" * 55)
    print("AdCopilot Evaluation Framework")
    print("Run: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 55)

    # Load test cases
    with open("data/eval_dataset.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    test_cases = dataset["test_cases"]
    print("Test cases: {}\n".format(len(test_cases)))

    results     = []
    passed      = 0
    failed      = 0
    errors      = 0

    for i, tc in enumerate(test_cases):
        tc_id    = tc["id"]
        product  = tc["product"]
        ad_copy  = tc["ad_copy"]
        weakness = tc["weakness_type"]

        print("[{}/{}] {} — {}".format(i+1, len(test_cases), tc_id, weakness))

        try:
            # STEP 1 — Score original ad
            print("  Scoring original...")
            before = calculate_explainable_score(ad_copy)
            if before.get("error"):
                raise Exception("Scorer failed: {}".format(before.get("error_msg")))

            before_score = before["total_score"]
            before_dims  = before["dimensions"]
            before_bench = calculate_benchmark(before_score, before_dims, product)
            before_pct   = before_bench["percentile"]

            print("  Before: {}/100 ({}th pct)".format(before_score, before_pct))

            # STEP 2 — Run AdCopilot pipeline
            print("  Running AdCopilot pipeline...")
            pipeline = run_full_pipeline(
                user_ad=ad_copy,
                product_description=product
            )

            if not pipeline.get("success", True):
                raise Exception("Pipeline failed")

            rewritten_ad = pipeline["rewritten_ad"]
            gaps         = pipeline["gaps"]

            # STEP 3 — Score rewritten ad
            print("  Scoring rewritten ad...")
            after = calculate_explainable_score(rewritten_ad)
            if after.get("error"):
                raise Exception("After scorer failed")

            after_score = after["total_score"]
            after_dims  = after["dimensions"]
            after_bench = calculate_benchmark(after_score, after_dims, product)
            after_pct   = after_bench["percentile"]

            print("  After:  {}/100 ({}th pct)".format(after_score, after_pct))

            # STEP 4 — Calculate metrics
            improvement    = after_score - before_score
            improvement_pct = round(improvement / before_score * 100, 1) if before_score > 0 else 0
            gap_fix_rate   = calculate_gap_fix_rate(before_dims, after_dims, gaps)
            status         = "PASS" if improvement >= 5 else "FAIL"

            if status == "PASS":
                passed += 1
                print("  Result: PASS (+{} pts)".format(improvement))
            else:
                failed += 1
                print("  Result: FAIL ({} pts)".format(improvement))

            # Dimension changes
            dim_changes = {}
            for bd in before_dims:
                dim_name = bd["dimension"]
                ad_score = next(
                    (d["score"] for d in after_dims if d["dimension"] == dim_name),
                    bd["score"]
                )
                dim_changes[dim_name] = {
                    "before": bd["score"],
                    "after":  ad_score,
                    "change": ad_score - bd["score"]
                }

            results.append({
                "id":               tc_id,
                "product":          product,
                "weakness_type":    weakness,
                "original_ad":      ad_copy,
                "rewritten_ad":     rewritten_ad,
                "before_score":     before_score,
                "after_score":      after_score,
                "improvement":      improvement,
                "improvement_pct":  improvement_pct,
                "before_percentile":before_pct,
                "after_percentile": after_pct,
                "gap_fix_rate":     gap_fix_rate,
                "gaps_identified":  len(gaps),
                "status":           status,
                "dimension_changes":dim_changes
            })

        except Exception as e:
            errors += 1
            print("  ERROR: {}".format(e))
            results.append({
                "id":            tc_id,
                "product":       product,
                "weakness_type": weakness,
                "status":        "ERROR",
                "error":         str(e)
            })

        time.sleep(2)
        print()

    # AGGREGATE METRICS
    valid = [r for r in results if r["status"] in ["PASS", "FAIL"]]

    if valid:
        improvements   = [r["improvement"] for r in valid]
        imp_pcts       = [r["improvement_pct"] for r in valid]
        gap_fix_rates  = [r["gap_fix_rate"] for r in valid]

        avg_improvement   = round(sum(improvements) / len(improvements), 1)
        avg_imp_pct       = round(sum(imp_pcts) / len(imp_pcts), 1)
        best_improvement  = max(improvements)
        worst_improvement = min(improvements)
        best_case         = next(r for r in valid if r["improvement"] == best_improvement)
        worst_case        = next(r for r in valid if r["improvement"] == worst_improvement)
        avg_gap_fix       = round(sum(gap_fix_rates) / len(gap_fix_rates), 1)
        success_rate      = round(passed / len(test_cases) * 100, 1)

        # Dimension avg improvements
        dim_names = [
            "Hook Strength", "Value Proposition", "Call to Action",
            "Emotional Trigger", "Clarity & Readability", "Length Optimization"
        ]
        dim_avg_improvements = {}
        for dim in dim_names:
            changes = [
                r["dimension_changes"][dim]["change"]
                for r in valid
                if "dimension_changes" in r and dim in r["dimension_changes"]
            ]
            dim_avg_improvements[dim] = round(sum(changes)/len(changes), 1) if changes else 0

        # Consistency std deviation
        mean = avg_improvement
        variance = sum((x - mean)**2 for x in improvements) / len(improvements)
        std_dev = round(variance ** 0.5, 1)

        summary = {
            "total_tests":           len(test_cases),
            "passed":                passed,
            "failed":                failed,
            "errors":                errors,
            "success_rate":          success_rate,
            "avg_improvement":       avg_improvement,
            "avg_improvement_pct":   avg_imp_pct,
            "best_improvement":      best_improvement,
            "best_case_id":          best_case["id"],
            "worst_improvement":     worst_improvement,
            "worst_case_id":         worst_case["id"],
            "avg_gap_fix_rate":      avg_gap_fix,
            "consistency_std":       std_dev,
            "dim_avg_improvements":  dim_avg_improvements
        }
    else:
        summary = {"error": "No valid results"}

    # SAVE
    run_id = "run_{}".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    output = {
        "run_id":  run_id,
        "run_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model":   "llama-3.3-70b-versatile",
        "summary": summary,
        "results": results
    }

    with open("data/eval_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # PRINT REPORT
    print("=" * 55)
    print("EVALUATION REPORT")
    print("=" * 55)
    if valid:
        print("Tests:           {}".format(len(test_cases)))
        print("Passed:          {} ({:.0f}%)".format(passed, success_rate))
        print("Failed:          {}".format(failed))
        print("Errors:          {}".format(errors))
        print()
        print("Avg Improvement: +{} pts".format(avg_improvement))
        print("Avg Improvement: +{}%".format(avg_imp_pct))
        print("Best:            {} +{} pts".format(best_case["id"], best_improvement))
        print("Worst:           {} +{} pts".format(worst_case["id"], worst_improvement))
        print("Avg Gap Fix:     {}%".format(avg_gap_fix))
        print("Consistency:     std={}".format(std_dev))
        print()
        print("DIMENSION IMPROVEMENTS (avg):")
        for dim, val in dim_avg_improvements.items():
            arrow = "+" if val > 0 else ""
            print("  {:<25} {}{}".format(dim, arrow, val))
        print()
        verdict = "IMPROVES" if success_rate >= 70 else "INCONSISTENT"
        print("VERDICT: AdCopilot {} ad quality in {}/{} cases".format(
            verdict, passed, len(test_cases)
        ))
    print("=" * 55)
    print("Saved: data/eval_results.json")

if __name__ == "__main__":
    run_evaluation()
