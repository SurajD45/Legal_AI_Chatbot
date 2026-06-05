#!/usr/bin/env python3
"""
Phase 9C: Multi-turn Conversational Evaluation Script
======================================================

Evaluates the full Phase 9 pipeline (Query Condenser + Context Expander)
against the `conversational_queries_v1.json` baseline dataset.

For each multi-turn conversation:
  1. Simulates sequential turns, maintaining in-memory chat history.
  2. Applies the Phase 9A keyword filter and query condenser on follow-up turns.
  3. Applies the Phase 9B context expander after retrieval.
  4. Evaluates the FINAL turn answer using the LLM judge (Faithfulness, Groundedness, Completeness).
  5. Records: original query, condensed query, sections retrieved, sections expanded, latencies.

Output: evaluation/reports/conversational_answer_quality_report.json
"""

import json
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows UTF-8 output compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.utils import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from app.core.retriever import get_retriever
from app.core.llm_chain import LLMChain
from app.core.query_condenser import get_query_condenser
from app.core.context_expander import get_context_expander
from evaluation.llm_judge import LLMJudge

DIVIDER = "=" * 72


# ---------------------------------------------------------------------------
# Single multi-turn conversation evaluation
# ---------------------------------------------------------------------------
def evaluate_conversation(
    conv_data: Dict,
    retriever: Any,
    llm: LLMChain,
    condenser: Any,
    expander: Any,
    judge: LLMJudge,
    cooldown: float = 2.0,
) -> Dict[str, Any]:
    """
    Runs a full multi-turn conversation and evaluates the FINAL turn.

    Returns a dict with per-turn metadata and final-turn quality scores.
    """
    conv_id = conv_data["id"]
    description = conv_data.get("description", "")
    turns = conv_data["conversation"]
    expected_per_turn = conv_data.get("expected_sections_per_turn", [[] for _ in turns])

    in_memory_history: List[Dict[str, str]] = []
    turn_results = []

    print(f"\n  Conversation {conv_id}: {description}")

    for turn_idx, user_query in enumerate(turns):
        is_last_turn = (turn_idx == len(turns) - 1)
        expected_sections = expected_per_turn[turn_idx] if turn_idx < len(expected_per_turn) else []

        print(f"    Turn {turn_idx + 1}/{len(turns)}: \"{user_query[:60]}\"")

        # ── Step 1: Query Condensation ────────────────────────────────────
        t_condense_start = time.perf_counter()
        condensation = condenser.condense(
            query=user_query,
            chat_history=in_memory_history,
        )
        condense_ms = int((time.perf_counter() - t_condense_start) * 1000)
        search_query = condensation["search_query"]
        was_condensed = condensation["condensed"]

        # ── Step 2: Retrieval ─────────────────────────────────────────────
        t_retrieve_start = time.perf_counter()
        try:
            documents = retriever.hybrid_search(search_query)
            retrieve_ms = int((time.perf_counter() - t_retrieve_start) * 1000)
            retrieved_sections = [doc.section for doc in documents]
        except Exception as e:
            retrieve_ms = 0
            documents = []
            retrieved_sections = []
            print(f"      [WARN] Retrieval failed: {e}")

        # ── Step 3: Context Expansion ─────────────────────────────────────
        t_expand_start = time.perf_counter()
        documents = expander.expand(documents)
        expand_ms = int((time.perf_counter() - t_expand_start) * 1000)
        expanded_sections = [doc.section for doc in documents]
        added_sections = [s for s in expanded_sections if s not in retrieved_sections]

        # ── Step 4: LLM Generation ────────────────────────────────────────
        t_gen_start = time.perf_counter()
        try:
            answer = llm.generate_answer(
                query=user_query,
                documents=documents,
                chat_history=in_memory_history,
            )
            gen_ms = int((time.perf_counter() - t_gen_start) * 1000)
        except Exception as e:
            gen_ms = 0
            answer = f"[ERROR] {e}"
            print(f"      [WARN] Generation failed: {e}")

        total_ms = condense_ms + retrieve_ms + expand_ms + gen_ms

        # ── Step 5: LLM Judge (FINAL turn only) ──────────────────────────
        judge_scores = None
        if is_last_turn:
            time.sleep(cooldown)  # Rate limit protection
            context_str = llm._build_context(documents)
            # Judge on the ORIGINAL user query (not condensed)
            raw_scores = judge.evaluate_answer(
                query=user_query,
                context=context_str,
                answer=answer,
            )
            judge_scores = {
                "faithfulness": raw_scores.get("faithfulness", {}).get("score", 0.0),
                "groundedness": raw_scores.get("groundedness", {}).get("score", 0.0),
                "completeness": raw_scores.get("completeness", {}).get("score", 0.0),
                "consistency": raw_scores.get("consistency", {}).get("score", 0.0),
                "faithfulness_evidence": raw_scores.get("faithfulness", {}).get("evidence", ""),
                "groundedness_evidence": raw_scores.get("groundedness", {}).get("evidence", ""),
                "completeness_evidence": raw_scores.get("completeness", {}).get("evidence", ""),
            }
            print(
                f"      [JUDGE] "
                f"F={judge_scores['faithfulness']:.2f} "
                f"G={judge_scores['groundedness']:.2f} "
                f"C={judge_scores['completeness']:.2f} "
                f"| condensed={was_condensed}"
            )

        # ── Step 6: Update in-memory chat history ─────────────────────────
        in_memory_history.append({"role": "user", "content": user_query})
        in_memory_history.append({"role": "assistant", "content": answer})

        turn_result = {
            "turn": turn_idx + 1,
            "user_query": user_query,
            "search_query": search_query,
            "was_condensed": was_condensed,
            "condense_ms": condense_ms,
            "retrieve_ms": retrieve_ms,
            "expand_ms": expand_ms,
            "gen_ms": gen_ms,
            "total_ms": total_ms,
            "retrieved_sections": retrieved_sections,
            "expanded_sections": expanded_sections,
            "added_by_expander": added_sections,
            "expected_sections": expected_sections,
            "section_hit": any(s in retrieved_sections + added_sections for s in expected_sections),
            "answer_preview": answer[:250] + "..." if len(answer) > 250 else answer,
        }

        if judge_scores:
            turn_result["judge_scores"] = judge_scores

        turn_results.append(turn_result)

        # Brief cooldown between turns (not last)
        if not is_last_turn:
            time.sleep(1.5)

    final_turn = turn_results[-1]
    judge = final_turn.get("judge_scores", {})

    return {
        "id": conv_id,
        "description": description,
        "num_turns": len(turns),
        "turns": turn_results,
        # Final turn summary (for easy aggregation)
        "final_query": final_turn["user_query"],
        "final_search_query": final_turn["search_query"],
        "final_condensed": final_turn["was_condensed"],
        "final_retrieved_sections": final_turn["retrieved_sections"],
        "final_expanded_sections": final_turn["expanded_sections"],
        "final_added_by_expander": final_turn["added_by_expander"],
        "final_section_hit": final_turn["section_hit"],
        # Quality scores
        "faithfulness": judge.get("faithfulness", 0.0),
        "groundedness": judge.get("groundedness", 0.0),
        "completeness": judge.get("completeness", 0.0),
        "consistency": judge.get("consistency", 0.0),
        # Latency breakdown
        "total_condense_ms": sum(t["condense_ms"] for t in turn_results),
        "avg_retrieve_ms": sum(t["retrieve_ms"] for t in turn_results) / len(turn_results),
        "avg_gen_ms": sum(t["gen_ms"] for t in turn_results) / len(turn_results),
        "final_turn_total_ms": final_turn["total_ms"],
    }


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------
def build_report(results: List[Dict]) -> Dict:
    evaluated = [r for r in results if "faithfulness" in r]
    errors = [r for r in results if "error" in r]
    n = len(evaluated)

    if n == 0:
        return {"error": "No conversations were successfully evaluated."}

    condensed_count = sum(1 for r in evaluated if r.get("final_condensed", False))
    section_hit_count = sum(1 for r in evaluated if r.get("final_section_hit", False))
    expansion_active = sum(1 for r in evaluated if r.get("final_added_by_expander"))

    avg_faithfulness = sum(r["faithfulness"] for r in evaluated) / n
    avg_groundedness = sum(r["groundedness"] for r in evaluated) / n
    avg_completeness = sum(r["completeness"] for r in evaluated) / n
    avg_consistency = sum(r["consistency"] for r in evaluated) / n
    avg_condense_ms = sum(r["total_condense_ms"] for r in evaluated) / n
    avg_retrieve_ms = sum(r["avg_retrieve_ms"] for r in evaluated) / n
    avg_gen_ms = sum(r["avg_gen_ms"] for r in evaluated) / n
    avg_total_ms = sum(r["final_turn_total_ms"] for r in evaluated) / n

    return {
        "summary": {
            "total_conversations": n,
            "errors": len(errors),
            "condensation_triggered": condensed_count,
            "condensation_rate": round(condensed_count / n, 2),
            "section_hit_rate": round(section_hit_count / n, 2),
            "expansion_active_count": expansion_active,
            # Quality metrics
            "avg_faithfulness": round(avg_faithfulness, 3),
            "avg_groundedness": round(avg_groundedness, 3),
            "avg_completeness": round(avg_completeness, 3),
            "avg_consistency": round(avg_consistency, 3),
            # Targets
            "target_completeness": 0.85,
            "target_groundedness": 0.90,
            "completeness_target_met": avg_completeness >= 0.85,
            "groundedness_target_met": avg_groundedness >= 0.90,
            # Latency
            "avg_condense_ms": round(avg_condense_ms, 1),
            "avg_retrieve_ms": round(avg_retrieve_ms, 1),
            "avg_gen_ms": round(avg_gen_ms, 1),
            "avg_final_turn_total_ms": round(avg_total_ms, 1),
        },
        "per_conversation": [
            {
                "id": r["id"],
                "description": r["description"],
                "final_query": r["final_query"],
                "search_query": r["final_search_query"],
                "condensed": r["final_condensed"],
                "section_hit": r["final_section_hit"],
                "retrieved": r["final_retrieved_sections"],
                "expanded": r["final_added_by_expander"],
                "faithfulness": r["faithfulness"],
                "groundedness": r["groundedness"],
                "completeness": r["completeness"],
                "condense_ms": r["total_condense_ms"],
                "final_turn_total_ms": r["final_turn_total_ms"],
            }
            for r in evaluated
        ],
        "failures": [
            {
                "id": r["id"],
                "description": r["description"],
                "final_query": r["final_query"],
                "faithfulness": r["faithfulness"],
                "groundedness": r["groundedness"],
                "completeness": r["completeness"],
            }
            for r in evaluated
            if r["faithfulness"] < 0.80 or r["completeness"] < 0.80
        ],
    }


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
def print_summary(report: Dict):
    s = report["summary"]
    print(f"\n{DIVIDER}")
    print("  PHASE 9C — CONVERSATIONAL EVALUATION RESULTS")
    print(DIVIDER)
    print(f"  Conversations Evaluated:    {s['total_conversations']}")
    print(f"  Condensation Triggered:     {s['condensation_triggered']} / {s['total_conversations']}  ({s['condensation_rate']*100:.0f}%)")
    print(f"  Expansion Active:           {s['expansion_active_count']} / {s['total_conversations']}")
    print(f"  Section Hit Rate:           {s['section_hit_rate']*100:.0f}%")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Avg Faithfulness:           {s['avg_faithfulness']:.3f}")
    print(f"  Avg Groundedness:           {s['avg_groundedness']:.3f}  {'✅' if s['groundedness_target_met'] else '⚠️  (target: 0.90)'}")
    print(f"  Avg Completeness:           {s['avg_completeness']:.3f}  {'✅' if s['completeness_target_met'] else '⚠️  (target: 0.85)'}")
    print(f"  Avg Consistency:            {s['avg_consistency']:.3f}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  Avg Condense Latency:       {s['avg_condense_ms']:.1f} ms")
    print(f"  Avg Retrieve Latency:       {s['avg_retrieve_ms']:.1f} ms")
    print(f"  Avg Generation Latency:     {s['avg_gen_ms']:.1f} ms")
    print(f"  Avg Final Turn Total:       {s['avg_final_turn_total_ms']:.1f} ms")
    print(DIVIDER)

    # Per-conversation table
    print(f"\n  {'ID':<4} {'Condensed':<10} {'Hit':<6} {'F':<6} {'G':<6} {'C':<6} Description")
    print(f"  {'─'*4} {'─'*10} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*40}")
    for r in report["per_conversation"]:
        cond = "YES" if r["condensed"] else "no"
        hit  = "✓" if r["section_hit"] else "✗"
        print(
            f"  {r['id']:<4} {cond:<10} {hit:<6} "
            f"{r['faithfulness']:.2f}  {r['groundedness']:.2f}  {r['completeness']:.2f}  "
            f"{r['description'][:45]}"
        )

    # Failures
    if report["failures"]:
        print(f"\n  ⚠️  LOW QUALITY RESULTS ({len(report['failures'])} conversations):")
        for f in report["failures"]:
            print(f"    [{f['id']}] \"{f['final_query']}\"")
            print(f"         F={f['faithfulness']:.2f}  G={f['groundedness']:.2f}  C={f['completeness']:.2f}")
    else:
        print(f"\n  ✅ No low-quality results detected!")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Phase 9C: Multi-turn conversational evaluation"
    )
    parser.add_argument(
        "--dataset",
        default="evaluation/conversational_queries_v1.json",
        help="Path to conversational queries dataset",
    )
    parser.add_argument(
        "--output",
        default="evaluation/reports/conversational_answer_quality_report.json",
        help="Path to save the report",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=3.0,
        help="Seconds to wait between LLM judge calls (default: 3.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of conversations (for quick tests)",
    )
    args = parser.parse_args()

    print(DIVIDER)
    print("  Legal AI Assistant — Phase 9C Conversational Evaluation")
    print(DIVIDER)

    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[FAIL] Dataset not found: {dataset_path}")
        sys.exit(1)

    with open(dataset_path, encoding="utf-8") as f:
        conversations = json.load(f)

    if args.limit:
        conversations = conversations[: args.limit]

    print(f"  Loaded {len(conversations)} conversations from {dataset_path.name}")

    # Initialize pipeline components
    print("\n  Initializing pipeline components...")
    retriever = get_retriever()
    llm = LLMChain()
    condenser = get_query_condenser()
    expander = get_context_expander()
    judge = LLMJudge()

    print(f"  [OK] Retriever      — BM25 + Qdrant hybrid search")
    print(f"  [OK] LLMChain       — model: {llm.model}")
    print(f"  [OK] QueryCondenser — model: {condenser.model}")
    print(f"  [OK] ContextExpander — {len(expander.section_map)} section pairs loaded")
    print(f"  [OK] LLMJudge       — model: {judge.model}")
    print(f"\n  Running {len(conversations)} conversations...\n")

    results = []
    for i, conv in enumerate(conversations, 1):
        print(f"\n[{i}/{len(conversations)}]", end="")
        try:
            result = evaluate_conversation(
                conv_data=conv,
                retriever=retriever,
                llm=llm,
                condenser=condenser,
                expander=expander,
                judge=judge,
                cooldown=args.cooldown,
            )
            results.append(result)
        except Exception as e:
            print(f"  [ERROR] Conversation {conv['id']} failed: {e}")
            results.append({"id": conv["id"], "error": str(e)})

        # Cooldown between conversations to protect rate limits
        if i < len(conversations):
            time.sleep(args.cooldown)

    # Build and print report
    report = build_report(results)
    if "error" in report:
        print(f"\n[FAIL] {report['error']}")
        sys.exit(1)

    print_summary(report)

    # Save report
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"report": report, "raw_results": results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n  [SAVED] Report written to: {out_path}")
    print(DIVIDER)


if __name__ == "__main__":
    main()
