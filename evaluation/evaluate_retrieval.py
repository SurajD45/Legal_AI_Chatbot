#!/usr/bin/env python3
"""
Retrieval Evaluation Script for Legal AI Assistant.

Measures how well the retriever finds the correct IPC sections.

Metrics:
- Recall@K: Fraction of expected sections found in top K results
- Mean Reciprocal Rank (MRR): Average of 1/rank of first correct result
- Exact Match Rate: How often the regex section detector fires correctly

Usage:
    python evaluation/evaluate_retrieval.py
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.retriever import DocumentRetriever
from app.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def load_test_queries(path: str = None) -> List[Dict]:
    """Load test queries from JSON file."""
    if path is None:
        path = str(Path(__file__).parent / "test_queries.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_recall_at_k(
    retrieved_sections: List[str],
    expected_sections: List[str],
    k: int,
) -> float:
    """Compute Recall@K: fraction of expected sections found in top K."""
    if not expected_sections:
        # Edge case: no expected sections (irrelevant query)
        # If retriever returns nothing, that's correct
        return 1.0 if not retrieved_sections else 0.0

    top_k = retrieved_sections[:k]
    found = sum(1 for s in expected_sections if s in top_k)
    return found / len(expected_sections)


def compute_mrr(
    retrieved_sections: List[str],
    expected_sections: List[str],
) -> float:
    """Compute Mean Reciprocal Rank for the first relevant result."""
    if not expected_sections:
        return 1.0 if not retrieved_sections else 0.0

    for rank, section in enumerate(retrieved_sections, 1):
        if section in expected_sections:
            return 1.0 / rank
    return 0.0


def evaluate_single_query(
    retriever: DocumentRetriever,
    query_data: Dict,
) -> Dict[str, Any]:
    """Evaluate a single query against the retriever."""
    query = query_data["query"]
    expected = query_data["expected_sections"]
    category = query_data.get("category", "unknown")

    # Test section detection (regex)
    detected_sections = retriever.detect_sections(query)

    # Run hybrid search
    start_time = time.time()
    try:
        results = retriever.hybrid_search(query)
        latency_ms = (time.time() - start_time) * 1000
        retrieved_sections = [doc.section for doc in results]
        error = None
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        retrieved_sections = []
        error = str(e)

    # Compute metrics
    recall_5 = compute_recall_at_k(retrieved_sections, expected, k=5)
    recall_10 = compute_recall_at_k(retrieved_sections, expected, k=10)
    mrr = compute_mrr(retrieved_sections, expected)

    # Check if regex detection found expected sections
    regex_hit = bool(detected_sections) and any(
        s in detected_sections for s in expected
    )

    return {
        "id": query_data["id"],
        "query": query,
        "category": category,
        "expected_sections": expected,
        "detected_sections": detected_sections,
        "retrieved_sections": retrieved_sections,
        "recall_at_5": recall_5,
        "recall_at_10": recall_10,
        "mrr": mrr,
        "regex_hit": regex_hit,
        "latency_ms": round(latency_ms, 1),
        "error": error,
    }


def generate_report(results: List[Dict]) -> Dict[str, Any]:
    """Generate aggregate report from individual results."""
    total = len(results)
    errors = sum(1 for r in results if r["error"])

    # Overall metrics
    avg_recall_5 = sum(r["recall_at_5"] for r in results) / total
    avg_recall_10 = sum(r["recall_at_10"] for r in results) / total
    avg_mrr = sum(r["mrr"] for r in results) / total
    avg_latency = sum(r["latency_ms"] for r in results) / total

    # Perfect recall count
    perfect_5 = sum(1 for r in results if r["recall_at_5"] == 1.0)
    perfect_10 = sum(1 for r in results if r["recall_at_10"] == 1.0)

    # Regex detection accuracy (for queries with sections in them)
    section_queries = [r for r in results if r["category"].startswith("exact_match")]
    regex_accuracy = (
        sum(1 for r in section_queries if r["regex_hit"]) / len(section_queries)
        if section_queries
        else 0
    )

    # Per-category breakdown
    categories = defaultdict(list)
    for r in results:
        categories[r["category"]].append(r)

    category_stats = {}
    for cat, cat_results in sorted(categories.items()):
        cat_total = len(cat_results)
        category_stats[cat] = {
            "count": cat_total,
            "avg_recall_5": round(
                sum(r["recall_at_5"] for r in cat_results) / cat_total, 3
            ),
            "avg_recall_10": round(
                sum(r["recall_at_10"] for r in cat_results) / cat_total, 3
            ),
            "avg_mrr": round(
                sum(r["mrr"] for r in cat_results) / cat_total, 3
            ),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in cat_results) / cat_total, 1
            ),
        }

    # Failed queries (recall@5 == 0 and had expected sections)
    failures = [
        {
            "id": r["id"],
            "query": r["query"],
            "expected": r["expected_sections"],
            "got": r["retrieved_sections"][:5],
        }
        for r in results
        if r["recall_at_5"] == 0.0 and r["expected_sections"]
    ]

    return {
        "summary": {
            "total_queries": total,
            "errors": errors,
            "avg_recall_at_5": round(avg_recall_5, 3),
            "avg_recall_at_10": round(avg_recall_10, 3),
            "avg_mrr": round(avg_mrr, 3),
            "perfect_recall_at_5": f"{perfect_5}/{total}",
            "perfect_recall_at_10": f"{perfect_10}/{total}",
            "regex_detection_accuracy": round(regex_accuracy, 3),
            "avg_latency_ms": round(avg_latency, 1),
        },
        "category_breakdown": category_stats,
        "failures": failures[:20],  # Top 20 failures
    }


def main():
    print("=" * 60)
    print("  Legal AI Assistant — Retrieval Evaluation")
    print("=" * 60)

    queries = load_test_queries()
    print(f"\nLoaded {len(queries)} test queries")

    retriever = DocumentRetriever()

    # Verify connection
    try:
        retriever.client.get_collections()
        print("✅ Qdrant connection OK")
    except Exception as e:
        print(f"❌ Qdrant connection failed: {e}")
        sys.exit(1)

    print(f"\nRunning evaluation...\n")

    results = []
    for i, query_data in enumerate(queries, 1):
        result = evaluate_single_query(retriever, query_data)
        results.append(result)

        # Progress indicator
        status = "✅" if result["recall_at_5"] >= 0.5 else "⚠️" if result["recall_at_5"] > 0 else "❌"
        print(
            f"  [{i:3d}/{len(queries)}] {status} "
            f"R@5={result['recall_at_5']:.2f} "
            f"MRR={result['mrr']:.2f} "
            f"({result['latency_ms']:.0f}ms) "
            f"| {result['query'][:50]}"
        )

    # Generate report
    report = generate_report(results)

    # Print summary
    s = report["summary"]
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Total Queries:         {s['total_queries']}")
    print(f"  Errors:                {s['errors']}")
    print(f"  Avg Recall@5:          {s['avg_recall_at_5']}")
    print(f"  Avg Recall@10:         {s['avg_recall_at_10']}")
    print(f"  Avg MRR:               {s['avg_mrr']}")
    print(f"  Perfect Recall@5:      {s['perfect_recall_at_5']}")
    print(f"  Perfect Recall@10:     {s['perfect_recall_at_10']}")
    print(f"  Regex Detection Acc:   {s['regex_detection_accuracy']}")
    print(f"  Avg Latency:           {s['avg_latency_ms']}ms")

    print("\n  Category Breakdown:")
    print(f"  {'Category':<25} {'Count':>5} {'R@5':>6} {'R@10':>6} {'MRR':>6} {'Latency':>8}")
    print(f"  {'-'*25} {'-'*5} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")
    for cat, stats in report["category_breakdown"].items():
        print(
            f"  {cat:<25} {stats['count']:>5} "
            f"{stats['avg_recall_5']:>6.3f} "
            f"{stats['avg_recall_10']:>6.3f} "
            f"{stats['avg_mrr']:>6.3f} "
            f"{stats['avg_latency_ms']:>7.1f}ms"
        )

    if report["failures"]:
        print(f"\n  Top Failures (Recall@5 = 0):")
        for f in report["failures"][:10]:
            print(f"    ❌ [{f['id']}] {f['query'][:45]}")
            print(f"       Expected: {f['expected']}, Got: {f['got']}")

    # Save full report
    output_path = Path(__file__).parent / "retrieval_report.json"
    full_output = {"report": report, "details": results}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Full report saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
