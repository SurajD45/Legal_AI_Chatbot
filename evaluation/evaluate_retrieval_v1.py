#!/usr/bin/env python3
"""
Phase 1 RAG Retrieval & Latency Evaluator for Legal AI Assistant.

Measures retriever quality and system latency for the v1 20-query dataset.
Calculates:
- Recall@1, Recall@5, Recall@10
- Mean Reciprocal Rank (MRR)
- Latency: retrieval_ms, generation_ms, total_ms

Usage:
    python evaluation/evaluate_retrieval_v1.py
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
from app.core.llm_chain import LLMChain
from app.utils import setup_logging, get_logger

# Reconfigure stdout/stderr to use UTF-8 for Windows compatibility with Hindi characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

setup_logging()
logger = get_logger(__name__)


def load_test_queries(path: str = None) -> List[Dict]:
    """Load test queries from JSON file."""
    if path is None:
        path = str(Path(__file__).parent / "test_queries_v1.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_recall_at_k(
    retrieved_sections: List[str],
    expected_sections: List[str],
    k: int,
) -> float:
    """Compute Recall@K: fraction of expected sections found in top K."""
    if not expected_sections:
        # Edge case: out of scope / no expected sections query
        # If retrieved sections is empty, that's perfect (1.0). Otherwise 0.0.
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
    llm: LLMChain,
    query_data: Dict,
) -> Dict[str, Any]:
    """Evaluate a single query against retriever and generation."""
    query = query_data["query"]
    expected = query_data["expected_sections"]
    category = query_data.get("category", "unknown")

    # Step 1: Retrieval
    start_time = time.time()
    try:
        results = retriever.hybrid_search(query)
        retrieval_ms = (time.time() - start_time) * 1000
        retrieved_sections = [doc.section for doc in results]
        retrieval_error = None
    except Exception as e:
        retrieval_ms = (time.time() - start_time) * 1000
        retrieved_sections = []
        retrieval_error = str(e)
        results = []

    # Step 2: Generation
    gen_start_time = time.time()
    answer_text = ""
    generation_error = None
    try:
        # Only call LLM if retrieval succeeded, otherwise empty answer
        if not retrieval_error:
            answer_text = llm.generate_answer(query=query, documents=results)
        generation_ms = (time.time() - gen_start_time) * 1000
    except Exception as e:
        generation_ms = (time.time() - gen_start_time) * 1000
        generation_error = str(e)

    total_ms = retrieval_ms + generation_ms

    # Compute metrics
    recall_1 = compute_recall_at_k(retrieved_sections, expected, k=1)
    recall_5 = compute_recall_at_k(retrieved_sections, expected, k=5)
    recall_10 = compute_recall_at_k(retrieved_sections, expected, k=10)
    mrr = compute_mrr(retrieved_sections, expected)

    # Check if we triggered section detection short-circuiting
    detected = retriever.detect_sections(query)
    short_circuited = bool(detected) and len(retrieved_sections) > 0

    return {
        "id": query_data["id"],
        "query": query,
        "category": category,
        "expected_sections": expected,
        "retrieved_sections": retrieved_sections,
        "recall_at_1": recall_1,
        "recall_at_5": recall_5,
        "recall_at_10": recall_10,
        "mrr": mrr,
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "total_ms": round(total_ms, 1),
        "short_circuited": short_circuited,
        "detected_sections": detected,
        "retrieval_error": retrieval_error,
        "generation_error": generation_error,
        "answer_snippet": answer_text[:100].replace("\n", " ") + "..." if answer_text else ""
    }


def generate_report(results: List[Dict]) -> Dict[str, Any]:
    """Generate aggregate report from individual query results."""
    total = len(results)
    
    # Calculate averages
    avg_recall_1 = sum(r["recall_at_1"] for r in results) / total
    avg_recall_5 = sum(r["recall_at_5"] for r in results) / total
    avg_recall_10 = sum(r["recall_at_10"] for r in results) / total
    avg_mrr = sum(r["mrr"] for r in results) / total
    avg_retrieval_ms = sum(r["retrieval_ms"] for r in results) / total
    avg_generation_ms = sum(r["generation_ms"] for r in results) / total
    avg_total_ms = sum(r["total_ms"] for r in results) / total

    # Breakdown by category
    categories = defaultdict(list)
    for r in results:
        categories[r["category"]].append(r)

    category_stats = {}
    for cat, cat_results in sorted(categories.items()):
        cat_total = len(cat_results)
        category_stats[cat] = {
            "count": cat_total,
            "avg_recall_1": round(sum(r["recall_at_1"] for r in cat_results) / cat_total, 3),
            "avg_recall_5": round(sum(r["recall_at_5"] for r in cat_results) / cat_total, 3),
            "avg_recall_10": round(sum(r["recall_at_10"] for r in cat_results) / cat_total, 3),
            "avg_mrr": round(sum(r["mrr"] for r in cat_results) / cat_total, 3),
            "avg_retrieval_ms": round(sum(r["retrieval_ms"] for r in cat_results) / cat_total, 1),
            "avg_generation_ms": round(sum(r["generation_ms"] for r in cat_results) / cat_total, 1),
            "avg_total_ms": round(sum(r["total_ms"] for r in cat_results) / cat_total, 1),
        }

    # Log specific failures (Recall@5 < 1.0 for queries expecting sections)
    failures = [
        {
            "id": r["id"],
            "query": r["query"],
            "category": r["category"],
            "expected": r["expected_sections"],
            "got": r["retrieved_sections"],
            "short_circuited": r["short_circuited"],
            "detected_sections": r["detected_sections"]
        }
        for r in results
        if r["recall_at_5"] < 1.0 and r["expected_sections"]
    ]

    return {
        "summary": {
            "total_queries": total,
            "avg_recall_at_1": round(avg_recall_1, 3),
            "avg_recall_at_5": round(avg_recall_5, 3),
            "avg_recall_at_10": round(avg_recall_10, 3),
            "avg_mrr": round(avg_mrr, 3),
            "avg_retrieval_ms": round(avg_retrieval_ms, 1),
            "avg_generation_ms": round(avg_generation_ms, 1),
            "avg_total_ms": round(avg_total_ms, 1),
        },
        "category_breakdown": category_stats,
        "failures": failures,
    }


def main():
    print("=" * 70)
    print("  Legal AI Assistant — Phase 1 Retrieval & Latency Evaluator")
    print("=" * 70)

    queries = load_test_queries()
    print(f"\nLoaded {len(queries)} test queries from test_queries_v1.json")

    retriever = DocumentRetriever()
    llm = LLMChain()

    # Validate connections
    try:
        retriever.client.get_collections()
        print("[OK] Qdrant Connection: OK")
    except Exception as e:
        print(f"[FAIL] Qdrant Connection Failed: {e}")
        sys.exit(1)

    print(f"[OK] LLM Chain Initialized: {settings.LLM_MODEL}\n")
    print("Running evaluation on 20 queries...\n")

    results = []
    for i, query_data in enumerate(queries, 1):
        result = evaluate_single_query(retriever, llm, query_data)
        results.append(result)

        # Status icon (ASCII only for Windows compatibility)
        if result["retrieval_error"] or result["generation_error"]:
            status = "ERR "
        elif result["recall_at_5"] == 1.0:
            status = "PASS"
        elif result["recall_at_5"] > 0.0:
            status = "WARN"
        else:
            status = "FAIL"

        sc_flag = "[SC]" if result["short_circuited"] else "    "
        print(
            f"  [{i:2d}/20] {status} {sc_flag} "
            f"R@1={result['recall_at_1']:.2f} "
            f"R@5={result['recall_at_5']:.2f} "
            f"MRR={result['mrr']:.2f} "
            f"| Ret: {result['retrieval_ms']:4.0f}ms | Gen: {result['generation_ms']:4.0f}ms "
            f"| {result['query'][:40]}"
        )
        time.sleep(0.5)  # Rate limit safety

    # Compute final reports
    report = generate_report(results)

    # Print summary
    s = report["summary"]
    print("\n" + "=" * 70)
    print("  EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Total Queries:         {s['total_queries']}")
    print(f"  Avg Recall@1:          {s['avg_recall_at_1']:.3f}")
    print(f"  Avg Recall@5:          {s['avg_recall_at_5']:.3f}")
    print(f"  Avg Recall@10:         {s['avg_recall_at_10']:.3f}")
    print(f"  Avg MRR:               {s['avg_mrr']:.3f}")
    print("-" * 70)
    print(f"  Avg Retrieval Latency: {s['avg_retrieval_ms']:.1f} ms")
    print(f"  Avg Generation Latency:{s['avg_generation_ms']:.1f} ms")
    print(f"  Avg Total Latency:     {s['avg_total_ms']:.1f} ms")
    print("=" * 70)

    print("\n  Category Performance Breakdown:")
    print(f"  {'Category':<22} | {'Count':<5} | {'R@1':<5} | {'R@5':<5} | {'R@10':<5} | {'MRR':<5} | {'Latency':<8}")
    print(f"  {'-'*22}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*8}")
    for cat, stats in report["category_breakdown"].items():
        print(
            f"  {cat:<22} | {stats['count']:<5d} | "
            f"{stats['avg_recall_1']:<5.2f} | "
            f"{stats['avg_recall_5']:<5.2f} | "
            f"{stats['avg_recall_10']:<5.2f} | "
            f"{stats['avg_mrr']:<5.2f} | "
            f"{stats['avg_total_ms']:>6.0f} ms"
        )

    # Detailed failures analysis
    if report["failures"]:
        print("\n" + "=" * 70)
        print("  RETRIEVAL FAILURES ANALYSIS (Recall@5 < 1.0)")
        print("=" * 70)
        for idx, f in enumerate(report["failures"], 1):
            sc_note = " (Triggered Short-Circuit Section Search)" if f["short_circuited"] else ""
            print(f"  {idx}. [{f['category']}] Query: \"{f['query']}\"")
            print(f"     Expected Sections: {f['expected']}")
            print(f"     Retrieved Sections: {f['got']}{sc_note}")
            if f["short_circuited"]:
                print(f"     ANALYSIS: Regex matched {f['detected_sections']} and skipped semantic lookup.")
            else:
                print(f"     ANALYSIS: Pure semantic lookup failed to retrieve all expected sections.")
            print()

    # Save reports
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    report_output_path = reports_dir / "retrieval_report_v1.json"
    static_expansion_output_path = results_dir / "static_expansion_v1.json"
    full_output = {
        "summary": s,
        "category_breakdown": report["category_breakdown"],
        "detailed_results": results,
        "failures": report["failures"]
    }
    
    with open(report_output_path, "w", encoding="utf-8") as out_f:
        json.dump(full_output, out_f, indent=2, ensure_ascii=False)
        
    with open(static_expansion_output_path, "w", encoding="utf-8") as out_f:
        json.dump(full_output, out_f, indent=2, ensure_ascii=False)

    print(f"[SAVED] Detailed evaluation log saved: {report_output_path}")
    print(f"[SAVED] Static expansion report saved: {static_expansion_output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
