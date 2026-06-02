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

def calculate_scope_handling_accuracy(details: List[Dict]) -> float:
    # Filter for out-of-scope queries (category == negative_queries)
    oos_queries = [r for r in details if r.get("category") == "negative_queries" and not r.get("error") and not r.get("skipped")]
    if not oos_queries:
        return 1.0
    correct = 0
    for r in oos_queries:
        answer = r.get("answer_text", "")
        has_deterministic = "OUT OF SCOPE NOTICE" in answer.upper() and "EXPLANATION" in answer.upper()
        has_judge = r.get("scope_handling", 0.0) >= 0.8
        if has_deterministic or has_judge:
            correct += 1
    return correct / len(oos_queries)

def main():
    p7_path = Path("evaluation/reports/answer_quality_pilot_report.json")
    p8_path = Path("evaluation/reports/answer_quality_report_v4.json")

    if not p7_path.exists():
        print(f"Error: Phase 7A report not found at {p7_path}")
        sys.exit(1)
    if not p8_path.exists():
        print(f"Error: Phase 8 report not found at {p8_path}")
        sys.exit(1)

    p7_data = load_json(p7_path)
    p8_data = load_json(p8_path)

    # In case report summaries are nested differently
    p7_summary = p7_data.get("report", {}).get("summary", p7_data.get("summary", {}))
    p8_summary = p8_data.get("report", {}).get("summary", p8_data.get("summary", {}))

    p7_details = p7_data.get("details", [])
    p8_details = p8_data.get("details", [])

    # Calculate Phase 7A Scope Handling Accuracy dynamically
    p7_scope_acc = calculate_scope_handling_accuracy(p7_details)
    p8_scope_acc = p8_summary.get("scope_handling_accuracy", calculate_scope_handling_accuracy(p8_details))

    # Calculate average word count for Phase 7A dynamically
    p7_evaluated = [r for r in p7_details if not r.get("error") and not r.get("skipped")]
    p7_avg_word = sum(len(r.get("answer_text", "").split()) for r in p7_evaluated) / len(p7_evaluated) if p7_evaluated else 0.0

    print("# Phase 8 Answer Quality & Scope Handling Evaluation Report\n")
    print("## 1. Overall Performance Comparison (Phase 7A vs Phase 8)\n")
    print("| Metric | Phase 7A | Phase 8 | Delta | Status |")
    print("|---|---|---|---|---|")

    metrics_to_compare = [
        ("Completeness", "avg_completeness", p7_summary.get("avg_completeness"), p8_summary.get("avg_completeness"), True, 0.85),
        ("Faithfulness", "avg_faithfulness", p7_summary.get("avg_faithfulness"), p8_summary.get("avg_faithfulness"), True, 0.90),
        ("Groundedness", "avg_groundedness", p7_summary.get("avg_groundedness"), p8_summary.get("avg_groundedness"), True, 0.90),
        ("Consistency", "avg_consistency", p7_summary.get("avg_consistency"), p8_summary.get("avg_consistency"), True, None),
        ("Hallucination Rate", "hallucination_rate", p7_summary.get("hallucination_rate"), p8_summary.get("hallucination_rate"), False, None),
        ("Citation Accuracy", "avg_citation_coverage", p7_summary.get("avg_citation_coverage"), p8_summary.get("avg_citation_coverage"), True, None),
        ("Scope Handling Accuracy", "scope_handling_accuracy", p7_scope_acc, p8_scope_acc, True, None),
    ]

    for label, key, p7_val, p8_val, higher_is_better, target in metrics_to_compare:
        delta = p8_val - p7_val
        if abs(delta) < 0.001:
            status = "⚪ Unchanged"
        elif (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
            status = "🟢 Improved"
        else:
            status = "🔴 Regressed"
            
        target_str = f" (Target: >={target:.2f})" if target else ""
        print(f"| {label}{target_str} | {p7_val:.3f} | {p8_val:.3f} | {delta:+.3f} | {status} |")

    # Length comparisons
    p7_len = p7_summary.get("avg_answer_length_chars")
    p8_len = p8_summary.get("avg_answer_length_chars")
    len_delta = p8_len - p7_len
    print(f"| Average Length (chars) | {p7_len:.0f} | {p8_len:.0f} | {len_delta:+.0f} | - |")

    p8_word = p8_summary.get("avg_answer_word_count", sum(r.get("answer_word_count", 0) for r in p8_details)/len(p8_details))
    word_delta = p8_word - p7_avg_word
    print(f"| Average Word Count | {p7_avg_word:.1f} | {p8_word:.1f} | {word_delta:+.1f} | - |")

    # Query level analysis
    p7_by_id = {q["id"]: q for q in p7_details}
    p8_by_id = {q["id"]: q for q in p8_details}

    improved = []
    unchanged = []
    regressed = []

    for qid, q8 in p8_by_id.items():
        q7 = p7_by_id.get(qid)
        if not q7 or q7.get("error") or q8.get("error"):
            continue
            
        comp_diff = q8["completeness"] - q7["completeness"]
        faith_diff = q8["faithfulness"] - q7["faithfulness"]
        ground_diff = q8["groundedness"] - q7["groundedness"]
        
        total_diff = comp_diff + faith_diff + ground_diff
        
        info = {
            "id": qid,
            "query": q8["query"],
            "category": q8["category"],
            "p7_comp": q7["completeness"],
            "p8_comp": q8["completeness"],
            "p7_faith": q7["faithfulness"],
            "p8_faith": q8["faithfulness"],
            "p7_ground": q7["groundedness"],
            "p8_ground": q8["groundedness"],
            "comp_diff": comp_diff,
            "faith_diff": faith_diff,
            "ground_diff": ground_diff,
        }
        
        if total_diff > 0.01:
            improved.append(info)
        elif total_diff < -0.01:
            regressed.append(info)
        else:
            unchanged.append(info)

    # Sort
    improved.sort(key=lambda x: (x["comp_diff"], x["faith_diff"], x["ground_diff"]), reverse=True)
    regressed.sort(key=lambda x: (x["comp_diff"], x["faith_diff"], x["ground_diff"]))
    unchanged.sort(key=lambda x: x["id"])

    print("\n## 2. Top Improved Answers\n")
    print("| ID | Category | Query | Completeness | Faithfulness | Groundedness | Delta (Comp / Faith / Ground) |")
    print("|---|---|---|---|---|---|---|")
    for q in improved[:10]:
        print(f"| {q['id']} | {q['category']} | \"{q['query']}\" | {q['p7_comp']:.2f} -> {q['p8_comp']:.2f} | {q['p7_faith']:.2f} -> {q['p8_faith']:.2f} | {q['p7_ground']:.2f} -> {q['p8_ground']:.2f} | {q['comp_diff']:+.2f} / {q['faith_diff']:+.2f} / {q['ground_diff']:+.2f} |")

    print("\n## 3. Unchanged Answers\n")
    print("| ID | Category | Query | Completeness | Faithfulness | Groundedness |")
    print("|---|---|---|---|---|---|")
    for q in unchanged[:10]:
        print(f"| {q['id']} | {q['category']} | \"{q['query']}\" | {q['p8_comp']:.2f} | {q['p8_faith']:.2f} | {q['p8_ground']:.2f} |")

    print("\n## 4. Regressed Answers\n")
    if regressed:
        print("| ID | Category | Query | Completeness | Faithfulness | Groundedness | Delta (Comp / Faith / Ground) |")
        print("|---|---|---|---|---|---|---|")
        for q in regressed[:10]:
            print(f"| {q['id']} | {q['category']} | \"{q['query']}\" | {q['p7_comp']:.2f} -> {q['p8_comp']:.2f} | {q['p7_faith']:.2f} -> {q['p8_faith']:.2f} | {q['p7_ground']:.2f} -> {q['p8_ground']:.2f} | {q['comp_diff']:+.2f} / {q['faith_diff']:+.2f} / {q['ground_diff']:+.2f} |")
    else:
        print("No regressions detected! Answer quality was maintained or improved across all queries.")

    print("\n## 5. Example Outputs Before (Phase 7A) vs After (Phase 8)\n")
    
    # Let's find one out of scope query and one missing context query
    oos_examples = [qid for qid, q8 in p8_by_id.items() if q8["category"] == "negative_queries" and qid in p7_by_id]
    missing_ctx_examples = [
        qid for qid, q8 in p8_by_id.items() 
        if q8["category"] in {"definition_queries", "punishment_queries"} 
        and qid in p7_by_id 
        and ("LIMITATIONS" in q8.get("answer_text", "") or "LIMITATIONS" in p7_by_id[qid].get("answer_text", ""))
    ]

    example_ids = []
    if oos_examples:
        example_ids.append(oos_examples[0])
    if missing_ctx_examples:
        example_ids.append(missing_ctx_examples[0])

    for qid in example_ids:
        q7 = p7_by_id[qid]
        q8 = p8_by_id[qid]
        print(f"### Query {qid}: \"{q8['query']}\"")
        print(f"**Category**: `{q8['category']}`\n")
        print("#### Phase 7A Output:")
        print("```markdown")
        print(q7.get("answer_text", "").strip())
        print("```\n")
        print("#### Phase 8 Output:")
        print("```markdown")
        print(q8.get("answer_text", "").strip())
        print("```\n")
        print("-" * 50 + "\n")

if __name__ == "__main__":
    main()
