import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Reconfigure stdout to use UTF-8 for Windows compatibility with Hindi characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    base_path = Path("evaluation/reports/retrieval_report_v2_run.json")
    v3_path = Path("evaluation/reports/retrieval_report_v3.json")

    if not base_path.exists():
        print(f"Error: Baseline report not found at {base_path}")
        sys.exit(1)
    if not v3_path.exists():
        print(f"Error: Phase 5 report not found at {v3_path}")
        sys.exit(1)

    base = load_json(base_path)
    v3 = load_json(v3_path)

    base_summary = base["summary"]
    v3_summary = v3["summary"]

    # 1. Overall Summary Deltas
    print("# Phase 5: Query Expansion & Legal Vocabulary Normalization Report\n")
    print("## 1. Overall Retrieval Metrics Deltas")
    print("| Metric | Baseline (v2) | Phase 5 (v3) | Delta | Status |")
    print("|---|---|---|---|---|")
    
    metrics = [
        ("Recall@1", "avg_recall_at_1"),
        ("Recall@5", "avg_recall_at_5"),
        ("Recall@10", "avg_recall_at_10"),
        ("MRR", "avg_mrr"),
        ("Precision@5", "avg_precision_at_5"),
        ("NDCG@5", "avg_ndcg_at_5"),
        ("NDCG@10", "avg_ndcg_at_10"),
    ]

    for label, key in metrics:
        b_val = base_summary[key]
        v_val = v3_summary[key]
        delta = v_val - b_val
        status = "🟢 Improved" if delta > 0.001 else ("🔴 Regressed" if delta < -0.001 else "⚪ Unchanged")
        print(f"| {label} | {b_val:.3f} | {v_val:.3f} | {delta:+.3f} | {status} |")

    b_lat = base_summary["avg_retrieval_ms"]
    v_lat = v3_summary["avg_retrieval_ms"]
    lat_delta = v_lat - b_lat
    lat_status = "🟢 Equivalent/Better" if lat_delta <= 10.0 else "⚠️ Slight Increase"
    print(f"| Avg Retrieval Latency | {b_lat:.1f} ms | {v_lat:.1f} ms | {lat_delta:+.1f} ms | {lat_status} |")

    # 2. Category-Level Breakdown
    print("\n## 2. Category-Level Performance Breakdown")
    print("| Category | Count | Base R@5 | v3 R@5 | R@5 Delta | Base NDCG@5 | v3 NDCG@5 | NDCG@5 Delta |")
    print("|---|---|---|---|---|---|---|---|")

    base_cats = base["category_breakdown"]
    v3_cats = v3["category_breakdown"]

    for cat in sorted(base_cats.keys()):
        b_cat = base_cats[cat]
        v_cat = v3_cats.get(cat, {})
        if not v_cat:
            continue
        
        b_r5 = b_cat["avg_recall_5"]
        v_r5 = v_cat["avg_recall_5"]
        r5_delta = v_r5 - b_r5

        b_n5 = b_cat["avg_ndcg_5"]
        v_n5 = v_cat["avg_ndcg_5"]
        n5_delta = v_n5 - b_n5

        print(f"| {cat} | {b_cat['count']} | {b_r5:.3f} | {v_r5:.3f} | {r5_delta:+.3f} | {b_n5:.3f} | {v_n5:.3f} | {n5_delta:+.3f} |")

    # 3. Query-by-Query Analysis
    base_queries = {q["id"]: q for q in base["detailed_results"]}
    v3_queries = {q["id"]: q for q in v3["detailed_results"]}

    query_deltas = []
    for qid, v3_q in v3_queries.items():
        base_q = base_queries.get(qid)
        if not base_q:
            continue
        
        r5_diff = v3_q["recall_at_5"] - base_q["recall_at_5"]
        n5_diff = v3_q["ndcg_at_5"] - base_q["ndcg_at_5"]
        mrr_diff = v3_q["mrr"] - base_q["mrr"]

        query_deltas.append({
            "id": qid,
            "query": v3_q["query"],
            "category": v3_q["category"],
            "base_r5": base_q["recall_at_5"],
            "v3_r5": v3_q["recall_at_5"],
            "r5_diff": r5_diff,
            "base_n5": base_q["ndcg_at_5"],
            "v3_n5": v3_q["ndcg_at_5"],
            "n5_diff": n5_diff,
            "base_mrr": base_q["mrr"],
            "v3_mrr": v3_q["mrr"],
            "mrr_diff": mrr_diff,
            "original_query": v3_q["original_query"],
            "expanded_query": v3_q["expanded_query"]
        })

    # Sort for improved queries: highest NDCG@5 delta first, then highest Recall@5 delta
    improved_queries = [qd for qd in query_deltas if qd["n5_diff"] > 0 or qd["r5_diff"] > 0]
    improved_queries.sort(key=lambda x: (x["n5_diff"], x["r5_diff"], x["mrr_diff"]), reverse=True)

    # Sort for unchanged queries (zero delta on both NDCG@5 and Recall@5)
    unchanged_queries = [qd for qd in query_deltas if abs(qd["n5_diff"]) < 0.001 and abs(qd["r5_diff"]) < 0.001]
    # Keep them ordered by ID
    unchanged_queries.sort(key=lambda x: x["id"])

    # Regressed queries check
    regressed_queries = [qd for qd in query_deltas if qd["n5_diff"] < 0 or qd["r5_diff"] < 0]
    regressed_queries.sort(key=lambda x: (x["n5_diff"], x["r5_diff"]), reverse=False)

    print("\n## 3. Top 20 Improved Queries")
    print("| ID | Category | Query | Base NDCG@5 | v3 NDCG@5 | Delta | Expansion |")
    print("|---|---|---|---|---|---|---|")
    for qd in improved_queries[:20]:
        exp_part = qd["expanded_query"][len(qd["original_query"]):].strip()
        exp_str = f"`{exp_part}`" if exp_part else "None"
        print(f"| {qd['id']} | {qd['category']} | \"{qd['original_query']}\" | {qd['base_n5']:.3f} | {qd['v3_n5']:.3f} | {qd['n5_diff']:+.3f} | {exp_str} |")

    print("\n## 4. Top 20 Unchanged Queries")
    print("| ID | Category | Query | NDCG@5 | Recall@5 | Expanded |")
    print("|---|---|---|---|---|---|")
    for qd in unchanged_queries[:20]:
        exp_part = qd["expanded_query"][len(qd["original_query"]):].strip()
        exp_str = f"`{exp_part}`" if exp_part else "None"
        print(f"| {qd['id']} | {qd['category']} | \"{qd['original_query']}\" | {qd['base_n5']:.3f} | {qd['base_r5']:.3f} | {exp_str} |")

    if regressed_queries:
        print("\n## ⚠️ Regressed Queries (Check for regressions)")
        print("| ID | Category | Query | Base NDCG@5 | v3 NDCG@5 | Delta |")
        print("|---|---|---|---|---|---|")
        for qd in regressed_queries[:20]:
            print(f"| {qd['id']} | {qd['category']} | \"{qd['original_query']}\" | {qd['base_n5']:.3f} | {qd['v3_n5']:.3f} | {qd['n5_diff']:+.3f} |")
    else:
        print("\n## 🟢 Regressions Check\nNo regressions detected! Accuracy maintained or improved across all queries.")

if __name__ == "__main__":
    main()
