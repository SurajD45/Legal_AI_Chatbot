"""
Phase 3A — Cross-Phase Comparison Report Generator
Compares: Baseline → E5 Fix → Hybrid RRF → Static Expansion
"""

import json, sys
sys.stdout.reconfigure(encoding='utf-8')

phases = [
    ("Baseline",         "evaluation/results/baseline_v1.json"),
    ("E5 Fix",           "evaluation/results/e5_fix_v1.json"),
    ("Hybrid RRF",       "evaluation/results/hybrid_rrf_v1.json"),
    ("Static Expansion", "evaluation/results/static_expansion_v1.json"),
]

data = {}
for name, path in phases:
    with open(path, "r", encoding="utf-8") as f:
        data[name] = json.load(f)

# --- Aggregate Metrics ---
print("=" * 80)
print("  AGGREGATE METRICS — ALL PHASES")
print("=" * 80)
print(f"  {'Phase':<20} | {'R@1':>6} | {'R@5':>6} | {'R@10':>6} | {'MRR':>6} | {'Latency':>10}")
print(f"  {'-'*20}-|-{'-'*6}-|-{'-'*6}-|-{'-'*6}-|-{'-'*6}-|-{'-'*10}")
for name, _ in phases:
    s = data[name]["summary"]
    print(f"  {name:<20} | {s['avg_recall_at_1']:>6.3f} | {s['avg_recall_at_5']:>6.3f} | {s['avg_recall_at_10']:>6.3f} | {s['avg_mrr']:>6.3f} | {s['avg_total_ms']:>8.0f} ms")

# --- Per-Query R@5 Comparison ---
print("\n" + "=" * 80)
print("  QUERY-BY-QUERY RECALL@5 COMPARISON")
print("=" * 80)
print(f"  {'ID':>3} | {'Category':<18} | {'Base':>5} | {'E5':>5} | {'RRF':>5} | {'Exp':>5} | {'Delta':>6} | Query")
print(f"  {'-'*3}-|-{'-'*18}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*6}-|-{'-'*30}")

for i in range(20):
    qid = i + 1
    results_by_phase = {}
    for name, _ in phases:
        for r in data[name]["detailed_results"]:
            if r["id"] == qid:
                results_by_phase[name] = r
                break

    base_r5 = results_by_phase.get("Baseline", {}).get("recall_at_5", 0)
    e5_r5 = results_by_phase.get("E5 Fix", {}).get("recall_at_5", 0)
    rrf_r5 = results_by_phase.get("Hybrid RRF", {}).get("recall_at_5", 0)
    exp_r5 = results_by_phase.get("Static Expansion", {}).get("recall_at_5", 0)
    delta = exp_r5 - rrf_r5
    
    query = results_by_phase.get("Static Expansion", {}).get("query", "")[:30]
    cat = results_by_phase.get("Static Expansion", {}).get("category", "")

    # Mark improvements and regressions
    if delta > 0:
        marker = f"+{delta:.2f}"
    elif delta < 0:
        marker = f"{delta:.2f}"
    else:
        marker = "  0.00"

    print(f"  {qid:>3} | {cat:<18} | {base_r5:>5.2f} | {e5_r5:>5.2f} | {rrf_r5:>5.2f} | {exp_r5:>5.2f} | {marker:>6} | {query}")

# --- Category Breakdown ---
print("\n" + "=" * 80)
print("  CATEGORY BREAKDOWN — RRF vs STATIC EXPANSION")
print("=" * 80)
cats = ["exact_match", "exact_match_hindi", "semantic", "semantic_hindi", "hinglish", "edge_case_no_match"]
print(f"  {'Category':<22} | {'RRF R@5':>8} | {'Exp R@5':>8} | {'RRF MRR':>8} | {'Exp MRR':>8}")
print(f"  {'-'*22}-|-{'-'*8}-|-{'-'*8}-|-{'-'*8}-|-{'-'*8}")
for cat in cats:
    rrf_cat = data["Hybrid RRF"]["category_breakdown"].get(cat, {})
    exp_cat = data["Static Expansion"]["category_breakdown"].get(cat, {})
    print(f"  {cat:<22} | {rrf_cat.get('avg_recall_5', 0):>8.3f} | {exp_cat.get('avg_recall_5', 0):>8.3f} | {rrf_cat.get('avg_mrr', 0):>8.3f} | {exp_cat.get('avg_mrr', 0):>8.3f}")

# --- Regression Check ---
print("\n" + "=" * 80)
print("  REGRESSION CHECK")
print("=" * 80)
regressions = 0
for i in range(20):
    qid = i + 1
    rrf_r5 = 0
    exp_r5 = 0
    query = ""
    for r in data["Hybrid RRF"]["detailed_results"]:
        if r["id"] == qid:
            rrf_r5 = r["recall_at_5"]
            query = r["query"]
            break
    for r in data["Static Expansion"]["detailed_results"]:
        if r["id"] == qid:
            exp_r5 = r["recall_at_5"]
            break
    if exp_r5 < rrf_r5:
        regressions += 1
        print(f"  REGRESSION Q{qid}: {query[:40]}  RRF={rrf_r5:.2f} -> Exp={exp_r5:.2f}")

if regressions == 0:
    print("  No regressions detected. All previously passing queries maintained.")

# --- Remaining Failures ---
print("\n" + "=" * 80)
print("  REMAINING FAILURES (Static Expansion)")
print("=" * 80)
for f in data["Static Expansion"]["failures"]:
    print(f"  Q{f['id']:2d} [{f['category']}] {f['query']}")
    print(f"       expected={f['expected']}  got={f['got']}")
    print()
