#!/usr/bin/env python3
"""
Answer Quality Evaluation Script for Legal AI Assistant.

Runs test queries through the full RAG pipeline (retrieve + generate)
and evaluates the quality of generated answers.

Checks:
- Does the answer mention expected IPC sections?
- Does the answer follow the structured format (PROVISIONS / ANALYSIS / PUNISHMENT)?
- Are there potential hallucinations (sections not in retrieved context)?
- Response latency

Usage:
    python evaluation/evaluate_answers.py [--limit N]
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.retriever import DocumentRetriever
from app.core.llm_chain import LLMChain
from app.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def load_test_queries(path: str = None) -> List[Dict]:
    """Load test queries from JSON file."""
    if path is None:
        path = str(Path(__file__).parent / "test_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_sections_from_answer(answer: str) -> List[str]:
    """Extract all IPC section numbers mentioned in the answer."""
    pattern = r"(?:section|sec\.?)\s*([0-9]{1,3}[A-Z]?)"
    matches = re.findall(pattern, answer, flags=re.IGNORECASE)
    return list(set(matches))


def check_format_compliance(answer: str) -> Dict[str, bool]:
    """Check if the answer follows the expected structured format."""
    answer_upper = answer.upper()
    return {
        "has_provisions": "RELEVANT PROVISIONS" in answer_upper or "PROVISION" in answer_upper,
        "has_analysis": "ANALYSIS" in answer_upper,
        "has_punishment": "PUNISHMENT" in answer_upper or "PENALTY" in answer_upper,
        "uses_bullet_points": "- " in answer or "• " in answer,
    }


def detect_hallucinations(
    answer_sections: List[str],
    retrieved_sections: List[str],
    expected_sections: List[str],
) -> List[str]:
    """
    Find sections mentioned in the answer that were NOT in
    the retrieved context AND not in expected sections.
    """
    known = set(retrieved_sections) | set(expected_sections)
    return [s for s in answer_sections if s not in known]


def evaluate_single(
    retriever: DocumentRetriever,
    llm: LLMChain,
    query_data: Dict,
) -> Dict[str, Any]:
    """Evaluate a single query through the full RAG pipeline."""
    query = query_data["query"]
    expected = query_data["expected_sections"]
    category = query_data.get("category", "unknown")

    # Skip edge cases with no expected sections (irrelevant queries)
    if not expected:
        return {
            "id": query_data["id"],
            "query": query,
            "category": category,
            "skipped": True,
            "reason": "No expected sections (edge case query)",
        }

    # Step 1: Retrieve
    start = time.time()
    try:
        documents = retriever.hybrid_search(query)
    except Exception as e:
        return {
            "id": query_data["id"],
            "query": query,
            "category": category,
            "error": f"Retrieval failed: {e}",
        }
    retrieval_ms = (time.time() - start) * 1000

    retrieved_sections = [doc.section for doc in documents]

    # Step 2: Generate answer
    gen_start = time.time()
    try:
        answer = llm.generate_answer(query=query, documents=documents)
    except Exception as e:
        return {
            "id": query_data["id"],
            "query": query,
            "category": category,
            "error": f"LLM generation failed: {e}",
        }
    generation_ms = (time.time() - gen_start) * 1000
    total_ms = retrieval_ms + generation_ms

    # Step 3: Analyze answer quality
    answer_sections = extract_sections_from_answer(answer)
    format_check = check_format_compliance(answer)
    hallucinated = detect_hallucinations(answer_sections, retrieved_sections, expected)

    # Section coverage: how many expected sections appear in the answer
    sections_in_answer = [s for s in expected if s in answer_sections]
    section_coverage = len(sections_in_answer) / len(expected) if expected else 0

    # Format score (0-4)
    format_score = sum(format_check.values())

    return {
        "id": query_data["id"],
        "query": query,
        "category": category,
        "expected_sections": expected,
        "retrieved_sections": retrieved_sections,
        "answer_sections": answer_sections,
        "section_coverage": round(section_coverage, 3),
        "format_check": format_check,
        "format_score": f"{format_score}/4",
        "hallucinated_sections": hallucinated,
        "has_hallucinations": len(hallucinated) > 0,
        "answer_length": len(answer),
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "total_ms": round(total_ms, 1),
        "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
    }


def generate_report(results: List[Dict]) -> Dict:
    """Generate aggregate quality report."""
    # Filter out skipped and errored
    evaluated = [r for r in results if not r.get("skipped") and not r.get("error")]
    skipped = [r for r in results if r.get("skipped")]
    errors = [r for r in results if r.get("error")]

    if not evaluated:
        return {"error": "No queries were successfully evaluated"}

    total = len(evaluated)

    # Section coverage
    avg_coverage = sum(r["section_coverage"] for r in evaluated) / total

    # Format compliance
    format_scores = []
    for r in evaluated:
        fc = r["format_check"]
        format_scores.append(sum(fc.values()) / 4)
    avg_format = sum(format_scores) / total

    # Hallucination rate
    hallucination_count = sum(1 for r in evaluated if r["has_hallucinations"])
    hallucination_rate = hallucination_count / total

    # Latency
    avg_retrieval = sum(r["retrieval_ms"] for r in evaluated) / total
    avg_generation = sum(r["generation_ms"] for r in evaluated) / total
    avg_total = sum(r["total_ms"] for r in evaluated) / total

    # Answer length
    avg_length = sum(r["answer_length"] for r in evaluated) / total

    return {
        "summary": {
            "total_evaluated": total,
            "skipped": len(skipped),
            "errors": len(errors),
            "avg_section_coverage": round(avg_coverage, 3),
            "avg_format_compliance": round(avg_format, 3),
            "hallucination_rate": round(hallucination_rate, 3),
            "queries_with_hallucinations": hallucination_count,
            "avg_answer_length_chars": round(avg_length),
            "avg_retrieval_ms": round(avg_retrieval, 1),
            "avg_generation_ms": round(avg_generation, 1),
            "avg_total_ms": round(avg_total, 1),
        },
        "hallucination_details": [
            {
                "id": r["id"],
                "query": r["query"],
                "hallucinated": r["hallucinated_sections"],
            }
            for r in evaluated
            if r["has_hallucinations"]
        ][:10],
        "low_coverage_queries": [
            {
                "id": r["id"],
                "query": r["query"],
                "coverage": r["section_coverage"],
                "expected": r["expected_sections"],
                "in_answer": r["answer_sections"],
            }
            for r in evaluated
            if r["section_coverage"] < 0.5
        ][:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate answer quality")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of queries to evaluate (default: 20, use 100 for full run)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Legal AI Assistant — Answer Quality Evaluation")
    print("=" * 60)

    queries = load_test_queries()

    # Apply limit (LLM calls cost time)
    queries = queries[: args.limit]
    print(f"\nEvaluating {len(queries)} queries (use --limit N to change)")

    retriever = DocumentRetriever()
    llm = LLMChain()

    print(f"✅ Retriever initialized")
    print(f"✅ LLM initialized (model: {settings.LLM_MODEL})")
    print(f"\nRunning evaluation...\n")

    results = []
    for i, query_data in enumerate(queries, 1):
        result = evaluate_single(retriever, llm, query_data)
        results.append(result)

        if result.get("skipped"):
            print(f"  [{i:3d}/{len(queries)}] ⏭️  Skipped: {result['query'][:50]}")
        elif result.get("error"):
            print(f"  [{i:3d}/{len(queries)}] ❌ Error: {result['error'][:60]}")
        else:
            cov = result["section_coverage"]
            hall = "🔴" if result["has_hallucinations"] else "🟢"
            status = "✅" if cov >= 0.5 else "⚠️" if cov > 0 else "❌"
            print(
                f"  [{i:3d}/{len(queries)}] {status} "
                f"Coverage={cov:.2f} {hall} "
                f"Format={result['format_score']} "
                f"({result['total_ms']:.0f}ms) "
                f"| {result['query'][:45]}"
            )

        # Rate limit: small delay between LLM calls
        time.sleep(0.5)

    # Generate report
    report = generate_report(results)

    if "error" in report:
        print(f"\n❌ {report['error']}")
        sys.exit(1)

    s = report["summary"]
    print("\n" + "=" * 60)
    print("  ANSWER QUALITY REPORT")
    print("=" * 60)
    print(f"  Evaluated:             {s['total_evaluated']}")
    print(f"  Skipped:               {s['skipped']}")
    print(f"  Errors:                {s['errors']}")
    print(f"  Avg Section Coverage:  {s['avg_section_coverage']}")
    print(f"  Avg Format Compliance: {s['avg_format_compliance']}")
    print(f"  Hallucination Rate:    {s['hallucination_rate']}")
    print(f"  Avg Answer Length:     {s['avg_answer_length_chars']} chars")
    print(f"  Avg Retrieval Time:    {s['avg_retrieval_ms']}ms")
    print(f"  Avg Generation Time:   {s['avg_generation_ms']}ms")
    print(f"  Avg Total Latency:     {s['avg_total_ms']}ms")

    if report["hallucination_details"]:
        print(f"\n  ⚠️  Queries with Hallucinations:")
        for h in report["hallucination_details"][:5]:
            print(f"    [{h['id']}] {h['query'][:45]}")
            print(f"        Hallucinated sections: {h['hallucinated']}")

    if report["low_coverage_queries"]:
        print(f"\n  ⚠️  Low Coverage Queries (< 50%):")
        for q in report["low_coverage_queries"][:5]:
            print(f"    [{q['id']}] {q['query'][:45]}")
            print(f"        Expected: {q['expected']}, In answer: {q['in_answer']}")

    # Save report
    output_path = Path(__file__).parent / "answer_quality_report.json"
    full_output = {"report": report, "details": results}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Full report saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
