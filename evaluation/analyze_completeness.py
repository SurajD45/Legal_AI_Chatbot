import json
from pathlib import Path

def main():
    report_path = Path("evaluation/reports/answer_quality_report_v4.json")
    if not report_path.exists():
        print(f"Report not found at {report_path}")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    details = data.get("details", [])
    
    # Filter for queries that successfully generated an answer but have completeness < 0.80
    low_comp_queries = [
        q for q in details 
        if not q.get("error") and not q.get("skipped") and q.get("completeness", 1.0) < 0.80
    ]
    
    print(f"Total Low-Completeness Queries (< 0.80): {len(low_comp_queries)} out of {len(details)}")
    print("=" * 100)
    
    for idx, q in enumerate(low_comp_queries, 1):
        qid = q["id"]
        query = q["query"]
        category = q["category"]
        expected = q.get("expected_sections", [])
        retrieved = q.get("retrieved_sections", [])
        score = q["completeness"]
        evidence = q.get("completeness_evidence", "")
        
        # Identify missing expected sections
        missing_expected = [s for s in expected if s not in retrieved]
        
        print(f"{idx}. Query ID {qid} ({category}) | Completeness Score: {score}")
        print(f"   Query: \"{query}\"")
        print(f"   Expected: {expected} | Retrieved: {retrieved}")
        print(f"   Missing expected sections in retrieval: {missing_expected}")
        print(f"   Judge Evidence: {evidence}")
        print("-" * 100)

if __name__ == "__main__":
    main()
