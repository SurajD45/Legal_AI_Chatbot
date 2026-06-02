#!/usr/bin/env python3
"""
Upgraded Answer Quality Evaluation Script for Legal AI Assistant.

Runs representative pilot queries through the full RAG pipeline (retrieve + generate)
and evaluates answer quality using both rule-based and LLM-as-a-judge metrics.
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.retriever import get_retriever
from app.core.llm_chain import LLMChain
from evaluation.llm_judge import LLMJudge
from app.utils import setup_logging, get_logger

# Reconfigure stdout/stderr to use UTF-8 for Windows compatibility with Hindi characters
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

setup_logging()
logger = get_logger(__name__)


def load_test_queries(path: str) -> List[Dict]:
    """Load test queries from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_representative_queries(queries: List[Dict], limit: int) -> List[Dict]:
    """Select equal numbers of representative queries from each category deterministically."""
    by_category = defaultdict(list)
    for q in queries:
        by_category[q["category"]].append(q)
        
    selected = []
    if not by_category:
        return queries[:limit]
        
    per_cat = max(1, limit // len(by_category))
    
    # Sort categories to remain deterministic
    for cat in sorted(by_category.keys()):
        selected.extend(by_category[cat][:per_cat])
        
    # Backfill if we are slightly short of limit
    if len(selected) < limit:
        all_ids = {q["id"] for q in selected}
        for q in queries:
            if q["id"] not in all_ids:
                selected.append(q)
                if len(selected) == limit:
                    break
                    
    return selected[:limit]


def extract_sections_from_answer(answer: str) -> List[str]:
    """Extract all IPC section numbers mentioned in the answer."""
    pattern = r"(?:section|sec\.?|u/s|धारा|कलम)\s*([0-9]{1,3}[A-Z]?)"
    matches = re.findall(pattern, answer, flags=re.IGNORECASE)
    # Also capture raw 3-digit numbers to be comprehensive, filtering common non-section numbers
    raw_numbers = re.findall(r"\b([0-9]{3}[A-Z]?)\b", answer)
    all_found = set(matches) | set(raw_numbers)
    # Ensure they are valid section strings
    valid_sections = []
    for s in all_found:
        s_clean = s.upper().strip()
        # Filter out years like 1860 or other unrelated numbers
        if s_clean not in {"186", "1860", "5000", "1000", "2000"}:
            valid_sections.append(s_clean)
    return list(set(valid_sections))


def detect_hallucinations(
    answer_sections: List[str],
    retrieved_sections: List[str],
    expected_sections: List[str],
) -> List[str]:
    """Find sections mentioned in the answer that were NOT in the retrieved context AND not in expected sections."""
    known = set(retrieved_sections) | set(expected_sections)
    return [s for s in answer_sections if s not in known]


def evaluate_single(
    retriever: Any,
    llm: LLMChain,
    judge: LLMJudge,
    query_data: Dict,
) -> Dict[str, Any]:
    """Evaluate a single query through full RAG and LLM judge."""
    query = query_data["query"]
    expected = query_data["expected_sections"]
    category = query_data.get("category", "unknown")
    difficulty = query_data.get("difficulty", "medium")
    language = query_data.get("language", "en")

    # Step 1: Retrieval
    start_time = time.time()
    try:
        documents = retriever.hybrid_search(query)
        retrieval_ms = (time.time() - start_time) * 1000
        retrieved_sections = [doc.section for doc in documents]
        retrieval_error = None
    except Exception as e:
        return {
            "id": query_data["id"],
            "query": query,
            "category": category,
            "error": f"Retrieval failed: {e}"
        }

    # Step 2: Generation
    gen_start = time.time()
    try:
        answer = llm.generate_answer(query=query, documents=documents)
        generation_ms = (time.time() - gen_start) * 1000
        generation_error = None
    except Exception as e:
        return {
            "id": query_data["id"],
            "query": query,
            "category": category,
            "error": f"Generation failed: {e}"
        }

    total_ms = retrieval_ms + generation_ms

    # Step 3: Rule-Based Evaluation
    answer_sections = extract_sections_from_answer(answer)
    hallucinated = detect_hallucinations(answer_sections, retrieved_sections, expected)

    # 1. Citation Coverage: cited sections in answer that exist in context
    if not answer_sections:
        citation_coverage = 1.0 if not expected else 0.0
    else:
        in_context = sum(1 for s in answer_sections if s in retrieved_sections)
        citation_coverage = in_context / len(answer_sections)

    # 2. Expected Section Coverage: expected sections cited in answer
    if not expected:
        expected_section_coverage = 1.0 if not answer_sections else 0.0
    else:
        cited_expected = sum(1 for s in expected if s in answer_sections)
        expected_section_coverage = cited_expected / len(expected)

    # 3. Retrieved Section Usage: retrieved sections cited in answer
    if not retrieved_sections:
        retrieved_section_usage = 1.0
    else:
        cited_retrieved = sum(1 for s in retrieved_sections if s in answer_sections)
        retrieved_section_usage = cited_retrieved / len(retrieved_sections)

    # Small sleep to protect Groq RPM limits between generate and judge
    time.sleep(2.0)

    # Step 4: LLM Judge Evaluation
    context_str = llm._build_context(documents)
    judge_eval = judge.evaluate_answer(query=query, context=context_str, answer=answer)

    faithfulness = judge_eval.get("faithfulness", {}).get("score", 0.0)
    faithfulness_evidence = judge_eval.get("faithfulness", {}).get("evidence", "")

    groundedness = judge_eval.get("groundedness", {}).get("score", 0.0)
    groundedness_evidence = judge_eval.get("groundedness", {}).get("evidence", "")

    completeness = judge_eval.get("completeness", {}).get("score", 0.0)
    completeness_evidence = judge_eval.get("completeness", {}).get("evidence", "")

    consistency = judge_eval.get("consistency", {}).get("score", 0.0)
    consistency_evidence = judge_eval.get("consistency", {}).get("evidence", "")

    scope_handling = judge_eval.get("scope_handling", {}).get("score", 0.0)
    scope_handling_evidence = judge_eval.get("scope_handling", {}).get("evidence", "")

    # Hallucination flag: check if either cited hallucinated sections exist OR faithfulness is low
    has_hallucinations = len(hallucinated) > 0 or faithfulness < 0.8

    # Word and token counts
    answer_word_count = len(answer.split())
    token_usage = getattr(llm, "last_token_usage", None)
    answer_token_count = token_usage.get("completion_tokens") if token_usage else None

    return {
        "id": query_data["id"],
        "query": query,
        "category": category,
        "difficulty": difficulty,
        "language": language,
        "expected_sections": expected,
        "retrieved_sections": retrieved_sections,
        "answer_sections": answer_sections,
        # Rule-Based metrics
        "citation_coverage": round(citation_coverage, 3),
        "expected_section_coverage": round(expected_section_coverage, 3),
        "retrieved_section_usage": round(retrieved_section_usage, 3),
        # LLM Judge metrics
        "faithfulness": faithfulness,
        "faithfulness_evidence": faithfulness_evidence,
        "groundedness": groundedness,
        "groundedness_evidence": groundedness_evidence,
        "completeness": completeness,
        "completeness_evidence": completeness_evidence,
        "consistency": consistency,
        "consistency_evidence": consistency_evidence,
        "scope_handling": scope_handling,
        "scope_handling_evidence": scope_handling_evidence,
        # Metadata
        "hallucinated_sections": hallucinated,
        "has_hallucinations": has_hallucinations,
        "answer_length": len(answer),
        "answer_word_count": answer_word_count,
        "answer_token_count": answer_token_count,
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "total_ms": round(total_ms, 1),
        "answer_text": answer,
        "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
    }


def generate_report(results: List[Dict]) -> Dict[str, Any]:
    """Compile overall summary and details report."""
    evaluated = [r for r in results if not r.get("skipped") and not r.get("error")]
    skipped = [r for r in results if r.get("skipped")]
    errors = [r for r in results if r.get("error")]

    if not evaluated:
        return {"error": "No queries were successfully evaluated"}

    total = len(evaluated)

    # Average metrics
    avg_faithfulness = sum(r["faithfulness"] for r in evaluated) / total
    avg_groundedness = sum(r["groundedness"] for r in evaluated) / total
    avg_completeness = sum(r["completeness"] for r in evaluated) / total
    avg_consistency = sum(r["consistency"] for r in evaluated) / total
    avg_scope_handling = sum(r["scope_handling"] for r in evaluated) / total

    avg_citation_coverage = sum(r["citation_coverage"] for r in evaluated) / total
    avg_expected_section_coverage = sum(r["expected_section_coverage"] for r in evaluated) / total
    avg_retrieved_section_usage = sum(r["retrieved_section_usage"] for r in evaluated) / total

    hallucination_count = sum(1 for r in evaluated if r["has_hallucinations"])
    hallucination_rate = hallucination_count / total

    avg_retrieval = sum(r["retrieval_ms"] for r in evaluated) / total
    avg_generation = sum(r["generation_ms"] for r in evaluated) / total
    avg_total = sum(r["total_ms"] for r in evaluated) / total
    avg_length = sum(r["answer_length"] for r in evaluated) / total
    avg_word_count = sum(r.get("answer_word_count", 0) for r in evaluated) / total
    token_counts = [r.get("answer_token_count") for r in evaluated if r.get("answer_token_count") is not None]
    avg_token_count = sum(token_counts) / len(token_counts) if token_counts else None

    # Scope Handling Accuracy
    out_of_scope_evaluated = [r for r in evaluated if r["category"] == "negative_queries"]
    if out_of_scope_evaluated:
        correct_oos_count = 0
        for r in out_of_scope_evaluated:
            answer = r.get("answer_text", "")
            # Deterministic check: must contain the headers of the out-of-scope notice template
            has_deterministic = "OUT OF SCOPE NOTICE" in answer.upper() and "EXPLANATION" in answer.upper()
            
            # Secondary check: LLM judge score >= 0.8
            has_judge = r.get("scope_handling", 0.0) >= 0.8
            
            if has_deterministic or has_judge:
                correct_oos_count += 1
        scope_handling_accuracy = correct_oos_count / len(out_of_scope_evaluated)
    else:
        scope_handling_accuracy = 1.0

    # Category breakdown
    category_stats = defaultdict(list)
    for r in evaluated:
        category_stats[r["category"]].append(r)
        
    category_summary = {}
    for cat, cat_res in category_stats.items():
        cat_total = len(cat_res)
        cat_out_of_scope = [r for r in cat_res if r["category"] == "negative_queries"]
        if cat_out_of_scope:
            cat_correct_oos = sum(1 for r in cat_out_of_scope if ("OUT OF SCOPE NOTICE" in r.get("answer_text", "").upper() and "EXPLANATION" in r.get("answer_text", "").upper()) or r.get("scope_handling", 0.0) >= 0.8)
            cat_scope_handling_accuracy = cat_correct_oos / len(cat_out_of_scope)
        else:
            cat_scope_handling_accuracy = 1.0

        category_summary[cat] = {
            "count": cat_total,
            "avg_faithfulness": round(sum(r["faithfulness"] for r in cat_res) / cat_total, 3),
            "avg_groundedness": round(sum(r["groundedness"] for r in cat_res) / cat_total, 3),
            "avg_completeness": round(sum(r["completeness"] for r in cat_res) / cat_total, 3),
            "avg_citation_coverage": round(sum(r["citation_coverage"] for r in cat_res) / cat_total, 3),
            "avg_section_coverage": round(sum(r["expected_section_coverage"] for r in cat_res) / cat_total, 3),
            "avg_scope_handling": round(sum(r["scope_handling"] for r in cat_res) / cat_total, 3),
            "scope_handling_accuracy": round(cat_scope_handling_accuracy, 3),
            "hallucination_rate": round(sum(1 for r in cat_res if r["has_hallucinations"]) / cat_total, 3),
        }

    return {
        "summary": {
            "total_evaluated": total,
            "skipped": len(skipped),
            "errors": len(errors),
            "avg_faithfulness": round(avg_faithfulness, 3),
            "avg_groundedness": round(avg_groundedness, 3),
            "avg_completeness": round(avg_completeness, 3),
            "avg_consistency": round(avg_consistency, 3),
            "avg_scope_handling": round(avg_scope_handling, 3),
            "scope_handling_accuracy": round(scope_handling_accuracy, 3),
            "avg_citation_coverage": round(avg_citation_coverage, 3),
            "avg_expected_section_coverage": round(avg_expected_section_coverage, 3),
            "avg_retrieved_section_usage": round(avg_retrieved_section_usage, 3),
            "hallucination_rate": round(hallucination_rate, 3),
            "queries_with_hallucinations": hallucination_count,
            "avg_answer_length_chars": round(avg_length),
            "avg_answer_word_count": round(avg_word_count, 1),
            "avg_answer_token_count": round(avg_token_count, 1) if avg_token_count is not None else None,
            "avg_retrieval_ms": round(avg_retrieval, 1),
            "avg_generation_ms": round(avg_generation, 1),
            "avg_total_ms": round(avg_total, 1),
        },
        "category_breakdown": category_summary,
        "failures": [
            {
                "id": r["id"],
                "query": r["query"],
                "category": r["category"],
                "faithfulness": r["faithfulness"],
                "groundedness": r["groundedness"],
                "completeness": r["completeness"],
                "expected": r["expected_sections"],
                "cited": r["answer_sections"],
                "faithfulness_evidence": r["faithfulness_evidence"],
                "completeness_evidence": r["completeness_evidence"],
            }
            for r in evaluated
            if r["faithfulness"] < 0.8 or r["completeness"] < 0.8 or r["has_hallucinations"]
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate answer quality")
    parser.add_argument(
        "--queries",
        type=str,
        default="evaluation/test_queries_v2.json",
        help="Path to queries JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/reports/answer_quality_pilot_report.json",
        help="Path to save report output"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Number of queries to evaluate (default: 30)"
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=2.0,
        help="Cooldown delay in seconds between queries"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Legal AI Assistant — Phase 7A Answer Quality Pilot Evaluation")
    print("=" * 70)

    # 1. Load Queries
    queries_path = Path(args.queries)
    if not queries_path.exists():
        print(f"[FAIL] Query file not found at: {queries_path}")
        sys.exit(1)
        
    all_queries = load_test_queries(str(queries_path))
    print(f"Loaded {len(all_queries)} queries from {queries_path.name}")

    # Select representative sample
    queries = select_representative_queries(all_queries, args.limit)
    print(f"Selected {len(queries)} representative pilot queries (3 per category)\n")

    # 2. Init components
    retriever = get_retriever()
    llm = LLMChain()
    judge = LLMJudge()

    print(f"[OK] Retriever Initialized")
    print(f"[OK] LLM Chain Initialized (model: {settings.LLM_MODEL})")
    print(f"[OK] LLM Judge Initialized (model: {settings.LLM_MODEL})")
    print(f"\nRunning evaluation on {len(queries)} pilot queries...\n")

    results = []
    for i, q_data in enumerate(queries, 1):
        if i == 1:
            time.sleep(2.0)
        result = evaluate_single(retriever, llm, judge, q_data)
        results.append(result)

        if result.get("error"):
            print(f"  [{i:2d}/{len(queries)}] ❌ Error: {result['error'][:60]}")
        else:
            print(
                f"  [{i:2d}/{len(queries)}] "
                f"F={result['faithfulness']:.2f} "
                f"G={result['groundedness']:.2f} "
                f"C={result['completeness']:.2f} "
                f"| CitCov={result['citation_coverage']:.2f} "
                f"| {result['query'][:45]}"
            )

        if args.cooldown > 0:
            time.sleep(args.cooldown)

    # 3. Generate and save report
    report = generate_report(results)
    if "error" in report:
        print(f"\n❌ {report['error']}")
        sys.exit(1)

    s = report["summary"]
    print("\n" + "=" * 70)
    print("  ANSWER QUALITY PILOT OVERALL SUMMARY")
    print("=" * 70)
    print(f"  Total Evaluated:              {s['total_evaluated']}")
    print(f"  Errors:                       {s['errors']}")
    print(f"  Avg Faithfulness (LLM):       {s['avg_faithfulness']:.3f}")
    print(f"  Avg Groundedness (LLM):       {s['avg_groundedness']:.3f}")
    print(f"  Avg Completeness (LLM):       {s['avg_completeness']:.3f}")
    print(f"  Avg Consistency (LLM):        {s['avg_consistency']:.3f}")
    print(f"  Avg Scope Handling (LLM):     {s['avg_scope_handling']:.3f}")
    print(f"  Scope Handling Accuracy:      {s['scope_handling_accuracy']:.3f}")
    print(f"  ------------------------------------------------")
    print(f"  Avg Citation Coverage (Rule): {s['avg_citation_coverage']:.3f}")
    print(f"  Avg Section Coverage (Rule):  {s['avg_expected_section_coverage']:.3f}")
    print(f"  Avg Retrieved Usage (Rule):   {s['avg_retrieved_section_usage']:.3f}")
    print(f"  ------------------------------------------------")
    print(f"  Hallucination Rate (Combined): {s['hallucination_rate']:.3f} ({s['queries_with_hallucinations']} queries)")
    print(f"  Avg Answer Length (chars):    {s['avg_answer_length_chars']}")
    print(f"  Avg Answer Word Count:        {s['avg_answer_word_count']:.1f}")
    if s['avg_answer_token_count'] is not None:
        print(f"  Avg Answer Token Count:       {s['avg_answer_token_count']:.1f}")
    print(f"  Avg Retrieval Latency:        {s['avg_retrieval_ms']:.1f} ms")
    print(f"  Avg Generation Latency:       {s['avg_generation_ms']:.1f} ms")
    print(f"  Avg Total Latency:            {s['avg_total_ms']:.1f} ms")
    print("=" * 70)

    # Print failures
    if report["failures"]:
        print(f"\n  ⚠️  LOW QUALITY / HALLUCINATED SAMPLES DETECTED ({len(report['failures'])} queries):")
        for f in report["failures"][:5]:
            print(f"    - Query: \"{f['query']}\"")
            print(f"      Expected: {f['expected']}, Cited: {f['cited']}")
            print(f"      Faithfulness: {f['faithfulness']} | Completeness: {f['completeness']}")
            print(f"      F-Evidence: {f['faithfulness_evidence']}")
            print(f"      C-Evidence: {f['completeness_evidence']}")
            print()

    # Save to file
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"report": report, "details": results}, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] Pilot evaluation report saved to: {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
