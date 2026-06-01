#!/usr/bin/env python3
"""
Upgraded RAG Retrieval Evaluator for Legal AI Assistant.

Measures retriever quality and latency across multiple dimensions (Language, Difficulty, Category).
Calculates:
- Recall@1, Recall@5, Recall@10
- Mean Reciprocal Rank (MRR)
- Precision@5
- NDCG@5, NDCG@10
- Latency: retrieval_ms, generation_ms, total_ms

Usage:
    python evaluation/evaluate_retrieval.py [--queries QUERY_JSON] [--output OUTPUT_JSON] [--retrieval-only] [--cooldown COOLDOWN_SEC]
"""

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.retriever import get_retriever
from app.core.llm_chain import get_llm_chain
from app.core.query_expander import expand_query
from app.utils import setup_logging, get_logger

# Reconfigure stdout/stderr to use UTF-8 for Windows compatibility with Hindi characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

setup_logging()
logger = get_logger(__name__)


def compute_recall_at_k(
    retrieved_sections: List[str],
    expected_sections: List[str],
    k: int,
) -> float:
    """Compute Recall@K: fraction of expected sections found in top K."""
    if not expected_sections:
        # Edge case: out of scope / no expected sections query
        return 1.0 if not retrieved_sections else 0.0

    top_k = retrieved_sections[:k]
    found = sum(1 for s in expected_sections if s in top_k)
    return found / len(expected_sections)


def compute_precision_at_k(
    retrieved_sections: List[str],
    expected_sections: List[str],
    k: int,
) -> float:
    """Compute Precision@K: fraction of retrieved sections in top K that are relevant."""
    top_k = retrieved_sections[:k]
    actual_k = len(top_k)
    if actual_k == 0:
        return 1.0 if not expected_sections else 0.0

    if not expected_sections:
        return 0.0

    found = sum(1 for s in top_k if s in expected_sections)
    return found / actual_k


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


def compute_ndcg_at_k(
    retrieved_sections: List[str],
    primary_sections: List[str],
    secondary_sections: List[str],
    k: int,
) -> float:
    """
    Compute Normalized Discounted Cumulative Gain (NDCG) at K.
    Relevance weights:
    - Primary expected sections: 2
    - Secondary expected sections: 1
    - Other sections: 0
    """
    if not primary_sections and not secondary_sections:
        # Out-of-scope query
        return 1.0 if not retrieved_sections else 0.0

    # Calculate DCG@K
    dcg = 0.0
    for idx, sec in enumerate(retrieved_sections[:k]):
        rel = 0.0
        if sec in primary_sections:
            rel = 2.0
        elif sec in secondary_sections:
            rel = 1.0

        gain = (2 ** rel) - 1
        discount = math.log2(idx + 2)
        dcg += gain / discount

    # Calculate IDCG@K (Ideal DCG@K)
    ideal_relevance = [2.0] * len(primary_sections) + [1.0] * len(secondary_sections)
    ideal_relevance.sort(reverse=True)

    idcg = 0.0
    for idx, rel in enumerate(ideal_relevance[:k]):
        gain = (2 ** rel) - 1
        discount = math.log2(idx + 2)
        idcg += gain / discount

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


def evaluate_single_query(
    retriever: Any,
    llm: Any,
    query_data: Dict,
    retrieval_only: bool,
) -> Dict[str, Any]:
    """Evaluate a single query against retriever and generation."""
    query = query_data["query"]
    expanded_q = expand_query(query)
    expected = query_data["expected_sections"]
    primary = query_data.get("primary_sections", expected)
    secondary = query_data.get("secondary_sections", [])
    category = query_data.get("category", "unknown")
    difficulty = query_data.get("difficulty", "medium")
    language = query_data.get("language", "en")

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

    # Step 2: Generation (if not retrieval_only)
    generation_ms = 0.0
    answer_text = ""
    generation_error = None

    if not retrieval_only and not retrieval_error:
        gen_start_time = time.time()
        try:
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
    precision_5 = compute_precision_at_k(retrieved_sections, expected, k=5)
    ndcg_5 = compute_ndcg_at_k(retrieved_sections, primary, secondary, k=5)
    ndcg_10 = compute_ndcg_at_k(retrieved_sections, primary, secondary, k=10)

    # Check if we triggered section detection short-circuiting
    detected = retriever.detect_sections(query)
    short_circuited = bool(detected) and len(retrieved_sections) > 0

    return {
        "id": query_data["id"],
        "query": query,
        "original_query": query,
        "expanded_query": expanded_q,
        "category": category,
        "difficulty": difficulty,
        "language": language,
        "expected_sections": expected,
        "primary_sections": primary,
        "secondary_sections": secondary,
        "retrieved_sections": retrieved_sections,
        "recall_at_1": recall_1,
        "recall_at_5": recall_5,
        "recall_at_10": recall_10,
        "mrr": mrr,
        "precision_at_5": precision_5,
        "ndcg_at_5": ndcg_5,
        "ndcg_at_10": ndcg_10,
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "total_ms": round(total_ms, 1),
        "short_circuited": short_circuited,
        "detected_sections": detected,
        "retrieval_error": retrieval_error,
        "generation_error": generation_error,
        "answer_snippet": answer_text[:100].replace("\n", " ") + "..." if answer_text else ""
    }


def aggregate_breakdown(results: List[Dict], key: str) -> Dict[str, Any]:
    """Group results by a specific metadata key and compile stats."""
    groups = defaultdict(list)
    for r in results:
        groups[r[key]].append(r)

    stats = {}
    for group_val, group_results in sorted(groups.items()):
        total = len(group_results)
        stats[group_val] = {
            "count": total,
            "avg_recall_1": round(sum(r["recall_at_1"] for r in group_results) / total, 3),
            "avg_recall_5": round(sum(r["recall_at_5"] for r in group_results) / total, 3),
            "avg_recall_10": round(sum(r["recall_at_10"] for r in group_results) / total, 3),
            "avg_mrr": round(sum(r["mrr"] for r in group_results) / total, 3),
            "avg_precision_5": round(sum(r["precision_at_5"] for r in group_results) / total, 3),
            "avg_ndcg_5": round(sum(r["ndcg_at_5"] for r in group_results) / total, 3),
            "avg_ndcg_10": round(sum(r["ndcg_at_10"] for r in group_results) / total, 3),
            "avg_retrieval_ms": round(sum(r["retrieval_ms"] for r in group_results) / total, 1),
            "avg_total_ms": round(sum(r["total_ms"] for r in group_results) / total, 1),
        }
    return stats


def generate_report(results: List[Dict]) -> Dict[str, Any]:
    """Generate aggregate report from individual query results."""
    total = len(results)

    avg_recall_1 = sum(r["recall_at_1"] for r in results) / total
    avg_recall_5 = sum(r["recall_at_5"] for r in results) / total
    avg_recall_10 = sum(r["recall_at_10"] for r in results) / total
    avg_mrr = sum(r["mrr"] for r in results) / total
    avg_precision_5 = sum(r["precision_at_5"] for r in results) / total
    avg_ndcg_5 = sum(r["ndcg_at_5"] for r in results) / total
    avg_ndcg_10 = sum(r["ndcg_at_10"] for r in results) / total
    avg_retrieval_ms = sum(r["retrieval_ms"] for r in results) / total
    avg_generation_ms = sum(r["generation_ms"] for r in results) / total
    avg_total_ms = sum(r["total_ms"] for r in results) / total

    category_stats = aggregate_breakdown(results, "category")
    difficulty_stats = aggregate_breakdown(results, "difficulty")
    language_stats = aggregate_breakdown(results, "language")

    # Logging failures (Recall@5 < 1.0 for queries expecting sections)
    failures = [
        {
            "id": r["id"],
            "query": r["query"],
            "original_query": r["original_query"],
            "expanded_query": r["expanded_query"],
            "category": r["category"],
            "difficulty": r["difficulty"],
            "language": r["language"],
            "expected": r["expected_sections"],
            "got": r["retrieved_sections"],
            "recall_at_5": r["recall_at_5"],
            "ndcg_at_5": r["ndcg_at_5"],
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
            "avg_precision_at_5": round(avg_precision_5, 3),
            "avg_ndcg_at_5": round(avg_ndcg_5, 3),
            "avg_ndcg_at_10": round(avg_ndcg_10, 3),
            "avg_retrieval_ms": round(avg_retrieval_ms, 1),
            "avg_generation_ms": round(avg_generation_ms, 1),
            "avg_total_ms": round(avg_total_ms, 1),
        },
        "category_breakdown": category_stats,
        "difficulty_breakdown": difficulty_stats,
        "language_breakdown": language_stats,
        "failures": failures,
        "detailed_results": results,
    }


def print_table(title: str, breakdown_stats: Dict[str, Any], group_col_name: str = "Dimension", group_col_width: int = 22):
    """Print clean alignment table to stdout."""
    print(f"\n  === {title} ===")
    headers = f"  {group_col_name:<{group_col_width}} | {'Count':<5} | {'R@1':<5} | {'R@5':<5} | {'R@10':<5} | {'MRR':<5} | {'P@5':<5} | {'NDCG@5':<6} | {'Latency':<8}"
    divider = f"  {'-'*group_col_width}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*5}-|-{'-'*6}-|-{'-'*8}"
    print(headers)
    print(divider)
    for key, stats in breakdown_stats.items():
        print(
            f"  {key:<{group_col_width}} | {stats['count']:<5d} | "
            f"{stats['avg_recall_1']:<5.2f} | "
            f"{stats['avg_recall_5']:<5.2f} | "
            f"{stats['avg_recall_10']:<5.2f} | "
            f"{stats['avg_mrr']:<5.2f} | "
            f"{stats['avg_precision_5']:<5.2f} | "
            f"{stats['avg_ndcg_5']:<6.2f} | "
            f"{stats['avg_retrieval_ms']:>6.0f} ms"
        )


def main():
    parser = argparse.ArgumentParser(description="Upgraded Legal AI Retriever Evaluator (v2)")
    parser.add_argument(
        "--queries",
        type=str,
        default="evaluation/test_queries_v2.json",
        help="Path to queries JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/reports/retrieval_report_v2.json",
        help="Path to save report output"
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Bypass LLM generation to evaluate retrieval speeds"
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=0.0,
        help="Wait time (seconds) between query execution loop"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("  Legal AI Assistant — Upgraded Retrieval Evaluator (v2)")
    print("=" * 80)

    # 1. Load Queries
    queries_path = Path(args.queries)
    if not queries_path.exists():
        print(f"[FAIL] Query file not found at: {queries_path}")
        sys.exit(1)

    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    total_queries = len(queries)
    print(f"\nLoaded {total_queries} queries from {queries_path.name}")

    # 2. Initialize Retriever & LLM
    retriever = get_retriever()
    
    llm = None
    if not args.retrieval_only:
        llm = get_llm_chain()
        print(f"[OK] LLM Chain Initialized: {settings.LLM_MODEL}")
    else:
        print("[INFO] Bypassing LLM generation (Retrieval-Only mode enabled)")

    # Validate Qdrant connection
    try:
        retriever.client.get_collections()
        print("[OK] Qdrant Connection: OK")
    except Exception as e:
        print(f"[FAIL] Qdrant Connection Failed: {e}")
        sys.exit(1)

    print(f"\nRunning benchmark on {total_queries} queries...\n")

    results = []
    len_digits = len(str(total_queries))
    
    for i, query_data in enumerate(queries, 1):
        result = evaluate_single_query(retriever, llm, query_data, args.retrieval_only)
        results.append(result)

        # Output status flag
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
            f"  [{i:{len_digits}d}/{total_queries}] {status} {sc_flag} "
            f"R@5={result['recall_at_5']:.2f} "
            f"MRR={result['mrr']:.2f} "
            f"P@5={result['precision_at_5']:.2f} "
            f"NDCG@5={result['ndcg_at_5']:.2f} "
            f"| Ret: {result['retrieval_ms']:4.0f}ms "
            f"| {result['query'][:35]}"
        )

        if args.cooldown > 0:
            time.sleep(args.cooldown)

    # 3. Compile report
    report = generate_report(results)
    s = report["summary"]

    # 4. Print Overall Summaries
    print("\n" + "=" * 80)
    print("  RETRIEVAL BENCHMARK OVERALL SUMMARY")
    print("=" * 80)
    print(f"  Total Queries Evaluated: {s['total_queries']}")
    print(f"  Avg Recall@1:            {s['avg_recall_at_1']:.3f}")
    print(f"  Avg Recall@5:            {s['avg_recall_at_5']:.3f}")
    print(f"  Avg Recall@10:           {s['avg_recall_at_10']:.3f}")
    print(f"  Avg MRR:                 {s['avg_mrr']:.3f}")
    print(f"  Avg Precision@5:         {s['avg_precision_at_5']:.3f}")
    print(f"  Avg NDCG@5:              {s['avg_ndcg_at_5']:.3f}")
    print(f"  Avg NDCG@10:             {s['avg_ndcg_at_10']:.3f}")
    print("-" * 80)
    print(f"  Avg Retrieval Latency:   {s['avg_retrieval_ms']:.1f} ms")
    if not args.retrieval_only:
        print(f"  Avg Generation Latency:  {s['avg_generation_ms']:.1f} ms")
        print(f"  Avg Total Latency:       {s['avg_total_ms']:.1f} ms")
    print("=" * 80)

    # 5. Print Multi-Dimensional Breakdowns
    print_table("CATEGORY PERFORMANCE BREAKDOWN", report["category_breakdown"], "Category", 25)
    print_table("DIFFICULTY PERFORMANCE BREAKDOWN", report["difficulty_breakdown"], "Difficulty", 15)
    print_table("LANGUAGE PERFORMANCE BREAKDOWN", report["language_breakdown"], "Language", 15)

    # 6. Failure Analysis log
    if report["failures"]:
        print("\n" + "=" * 80)
        print("  RETRIEVAL FAILURES DETAIL (Recall@5 < 1.0)")
        print("=" * 80)
        for idx, f in enumerate(report["failures"][:20], 1):  # Show top 20 failures
            print(f"  {idx}. [{f['category']} | {f['language']} | {f['difficulty']}] Query: \"{f['query']}\"")
            print(f"     Expected: {f['expected']}")
            print(f"     Retrieved: {f['got']} (R@5={f['recall_at_5']:.2f}, NDCG@5={f['ndcg_at_5']:.2f})")
            print()
        if len(report["failures"]) > 20:
            print(f"  ... and {len(report['failures']) - 20} more failures.")
            print("=" * 80)

    # 7. Save outputs
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(report, out_f, indent=2, ensure_ascii=False)
        
    print(f"\n[SAVED] Benchmark evaluation report saved to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
