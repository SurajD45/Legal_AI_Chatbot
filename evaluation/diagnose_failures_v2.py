"""
Phase 4: Failure Mode Classification Diagnostics.
Checks the rank and score of missing expected sections in:
1. Expanded query
2. Dense search (multilingual-e5-base) at Top-100
3. Sparse search (rank-bm25) at Top-100
4. Reciprocal Rank Fusion (RRF) at Top-100

Classifies each failure as:
- Ranking Problem: Section retrieved in Top-100 candidates (dense or sparse) but ranked > 5.
- Retrieval Problem: Section NOT retrieved in Top-100 candidates of either dense or sparse.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.retriever import DocumentRetriever
from app.core.query_expander import expand_query

def main():
    queries_path = Path(__file__).parent / "test_queries_v1.json"
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    # The 5 queries that fail to achieve Recall@5 = 1.0 in Phase 3A:
    target_ids = {7, 8, 13, 16, 17}
    failed_queries = [q for q in queries if q["id"] in target_ids]

    retriever = DocumentRetriever()

    print("=" * 80)
    print("  PHASE 4: FAILURE MODE DIAGNOSTICS & CLASSIFICATION (K=100)")
    print("=" * 80)

    classification_results = []

    for q in failed_queries:
        query_id = q["id"]
        raw_query = q["query"]
        expected = q["expected_sections"]
        category = q["category"]

        expanded = expand_query(raw_query)

        print(f"\n[{query_id}] Query: \"{raw_query}\"")
        print(f"    Expanded: \"{expanded}\"")
        print(f"    Expected: {expected}")

        # Get top-100 candidates for dense and sparse
        dense_results = retriever.semantic_search(expanded, top_k=100)
        bm25_results = retriever.bm25_search(expanded, top_k=100)

        # Get full RRF fusion of these 100 candidates
        fused_results = retriever.reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=bm25_results,
            k=60,
            top_k=100
        )

        dense_sections = [doc.section for doc in dense_results]
        bm25_sections = [doc.section for doc in bm25_results]
        fused_sections = [doc.section for doc in fused_results]

        for sec in expected:
            in_dense = sec in dense_sections
            in_bm25 = sec in bm25_sections
            in_fused = sec in fused_sections

            dense_rank = dense_sections.index(sec) + 1 if in_dense else None
            bm25_rank = bm25_sections.index(sec) + 1 if in_bm25 else None
            fused_rank = fused_sections.index(sec) + 1 if in_fused else None

            # Classification Logic
            if in_dense or in_bm25:
                status = "RANKING PROBLEM"
                reason = f"Surfaced in candidates (Dense rank: {dense_rank}, BM25 rank: {bm25_rank}), but RRF rank: {fused_rank} is > 5."
            else:
                status = "RETRIEVAL PROBLEM"
                reason = "Not surfaced in Top-100 candidates for either Dense or Sparse search."

            print(f"  - Section {sec:5s}: {status}")
            print(f"    -> Dense Rank: {dense_rank if in_dense else 'Not found'}")
            print(f"    -> BM25 Rank:  {bm25_rank if in_bm25 else 'Not found'}")
            print(f"    -> RRF Rank:   {fused_rank if in_fused else 'Not found'}")
            print(f"    -> Diagnosis:  {reason}")

            classification_results.append({
                "query_id": query_id,
                "query": raw_query,
                "section": sec,
                "in_dense": in_dense,
                "dense_rank": dense_rank,
                "in_bm25": in_bm25,
                "bm25_rank": bm25_rank,
                "in_fused": in_fused,
                "fused_rank": fused_rank,
                "status": status,
                "reason": reason
            })

    # Save diagnostics report to reports directory
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "failure_classification_v1.json"
    with open(report_file, "w", encoding="utf-8") as rf:
        json.dump(classification_results, rf, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"Diagnostics completed. Report saved to: {report_file.resolve()}")
    print("=" * 80)

if __name__ == "__main__":
    main()
