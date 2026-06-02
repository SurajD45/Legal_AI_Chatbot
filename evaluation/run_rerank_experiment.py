#!/usr/bin/env python3
"""
Controlled Reranker Effectiveness Experiment.

Runs baseline retrieval vs retrieval + reranking (BAAI/bge-reranker-base via HF API)
on a sample of 30 historical failures across 5 categories.
"""

import os
import sys
import json
import time
import httpx
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env variables explicitly
load_dotenv(dotenv_path="c:/Users/suraj doifode/Desktop/legal-ai-assistant/.env")

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.core.retriever import get_retriever
from app.core.query_expander import expand_query
from app.models import RetrievedDocument
from evaluation.evaluate_retrieval import (
    compute_recall_at_k,
    compute_mrr,
    compute_precision_at_k,
    compute_ndcg_at_k
)

# Configuration for HF API
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
RERANKER_MODEL = "BAAI/bge-reranker-base"
HF_RERANK_URL = f"https://router.huggingface.co/hf-inference/models/{RERANKER_MODEL}"

def call_hf_reranker(query: str, documents: List[RetrievedDocument]) -> List[float]:
    """Call HF Inference API to score query-document pairs."""
    if not documents:
        return []
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {HF_API_TOKEN}"
    }
    
    payload = {
        "inputs": [
            {
                "text": query[:250],
                "text_pair": f"{doc.title or ''} {doc.text or ''}"[:1000]
            }
            for doc in documents
        ]
    }
    
    # Set timeout to 2.0s, only retry once on 503 loading
    for attempt in range(2):
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.post(HF_RERANK_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    res_json = response.json()
                    if isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], list):
                        scores = [item["score"] for item in res_json[0]]
                        return scores
                elif response.status_code == 503 or "loading" in response.text.lower():
                    sleep_time = 4.0
                    print(f"    [HF API Loading] Model is starting up. Sleeping for {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"    [HF API Error] Code {response.status_code}: {response.text}")
                    break
        except httpx.ReadTimeout:
            print("    [HF API Timeout] Read operation timed out. Falling back.")
            break
        except Exception as e:
            print(f"    [HF API Exception] {e}")
            break
            
    # Return zero scores on failure (graceful degradation)
    return [0.0] * len(documents)


def select_30_failures(report_path: Path, queries_path: Path) -> List[Dict]:
    """Select exactly 30 failure queries from v2 report across 5 key dimensions."""
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)
        
    # Map of queries by ID
    query_map = {q["id"]: q for q in queries}
    
    # Filter failures (Recall@5 < 1.0)
    failures = [f for f in report["failures"] if f["recall_at_5"] < 1.0]
    
    print(f"Found {len(failures)} baseline failures.")
    
    # Categorize failures into target buckets
    buckets = {
        "definition_vs_punishment": [],  # from definition_queries and punishment_queries
        "hindi": [],                     # from hindi_semantic_queries
        "hinglish": [],                  # from hinglish_queries
        "synonym_paraphrase": [],        # from english_semantic_queries
        "ambiguous": []                  # from ambiguous_queries
    }
    
    for f in failures:
        q_id = f["id"]
        q_data = query_map.get(q_id)
        if not q_data:
            continue
            
        cat = q_data["category"]
        if cat in ("definition_queries", "punishment_queries"):
            buckets["definition_vs_punishment"].append(q_data)
        elif cat == "hindi_semantic_queries":
            buckets["hindi"].append(q_data)
        elif cat == "hinglish_queries":
            buckets["hinglish"].append(q_data)
        elif cat == "english_semantic_queries":
            buckets["synonym_paraphrase"].append(q_data)
        elif cat == "ambiguous_queries":
            buckets["ambiguous"].append(q_data)

    # Select exactly 6 from each bucket to make 30
    selected_queries = []
    for bucket_name, bucket_list in buckets.items():
        count = min(len(bucket_list), 6)
        print(f"  Category '{bucket_name}': Selected {count}/{len(bucket_list)} failures")
        selected_queries.extend(bucket_list[:count])
        
    # If we are short of 30, backfill from remaining failures
    if len(selected_queries) < 30:
        needed = 30 - len(selected_queries)
        all_bucketed_ids = {q["id"] for q in selected_queries}
        backfill = []
        for bucket_list in buckets.values():
            for q in bucket_list:
                if q["id"] not in all_bucketed_ids:
                    backfill.append(q)
        selected_queries.extend(backfill[:needed])
        
    print(f"Total queries selected for experiment: {len(selected_queries)}")
    return selected_queries, report, failures


def run_experiment():
    print("=" * 80)
    print("  Legal AI Assistant — Controlled Reranker Experiment")
    print("=" * 80)
    
    report_path = Path("evaluation/reports/retrieval_report_v2.json")
    queries_path = Path("evaluation/test_queries_v2.json")
    
    if not report_path.exists():
        print(f"[FAIL] Baseline report not found at: {report_path}")
        print("Please run evaluate_retrieval.py first.")
        sys.exit(1)
        
    # 1. Select 30 failure queries
    selected_queries, report, failures = select_30_failures(report_path, queries_path)
    
    # 2. Run retrieval
    retriever = get_retriever()
    
    results = []
    
    print("\nRunning live evaluation on selected queries...")
    for idx, q_data in enumerate(selected_queries, 1):
        query = q_data["query"]
        expected = q_data["expected_sections"]
        primary = q_data.get("primary_sections", expected)
        secondary = q_data.get("secondary_sections", [])
        
        print(f"\n  [{idx}/30] Query: \"{query}\"")
        
        # Retry loop to absorb DNS resolution failures or transient Qdrant connection drops
        for attempt in range(3):
            try:
                # 2a. Run Baseline Retrieval (RRF top 5)
                expanded = expand_query(query)
                dense_docs = retriever.semantic_search(expanded, top_k=20)
                sparse_docs = retriever.bm25_search(expanded, top_k=20)
                break
            except Exception as e:
                if attempt < 2:
                    print(f"    [Search Retry] Query failed ({e}). Sleeping 3s and retrying...")
                    time.sleep(3.0)
                else:
                    print(f"    [Search Failure] Query failed permanently: {e}")
                    raise e
                    
        # Baseline top 5
        baseline_docs = retriever.reciprocal_rank_fusion(
            dense_results=dense_docs,
            sparse_results=sparse_docs,
            k=settings.RRF_K,
            top_k=5
        )
        baseline_sections = [doc.section for doc in baseline_docs]
        
        # Calculate Baseline Metrics
        b_recall = compute_recall_at_k(baseline_sections, expected, k=5)
        b_mrr = compute_mrr(baseline_sections, expected)
        b_ndcg = compute_ndcg_at_k(baseline_sections, primary, secondary, k=5)
        
        # 2b. Run Retrieval + Reranking (top 15 RRF -> Rerank -> top 5)
        candidate_docs = retriever.reciprocal_rank_fusion(
            dense_results=dense_docs,
            sparse_results=sparse_docs,
            k=settings.RRF_K,
            top_k=15
        )
        
        # Score candidates via HF API
        rerank_start = time.time()
        scores = call_hf_reranker(query, candidate_docs)
        rerank_latency_ms = (time.time() - rerank_start) * 1000
        
        # Attach scores and sort
        for doc, score in zip(candidate_docs, scores):
            doc.score = score
            
        reranked_docs = sorted(candidate_docs, key=lambda x: x.score, reverse=True)
        reranked_docs = reranked_docs[:5]
        reranked_sections = [doc.section for doc in reranked_docs]
        
        # Calculate Reranked Metrics
        r_recall = compute_recall_at_k(reranked_sections, expected, k=5)
        r_mrr = compute_mrr(reranked_sections, expected)
        r_ndcg = compute_ndcg_at_k(reranked_sections, primary, secondary, k=5)
        
        # Compare
        recall_diff = r_recall - b_recall
        ndcg_diff = r_ndcg - b_ndcg
        
        status_msg = "STABLE"
        if recall_diff > 0 or ndcg_diff > 0:
            status_msg = "IMPROVED"
        elif recall_diff < 0 or ndcg_diff < 0:
            status_msg = "REGRESSED"
            
        print(f"    Baseline: R@5={b_recall:.2f} MRR={b_mrr:.2f} NDCG@5={b_ndcg:.2f} | Got: {baseline_sections}")
        print(f"    Reranked: R@5={r_recall:.2f} MRR={r_mrr:.2f} NDCG@5={r_ndcg:.2f} | Got: {reranked_sections}")
        print(f"    Result:   {status_msg} (Recall Delta: {recall_diff:+.2f}, NDCG Delta: {ndcg_diff:+.2f}) | Latency: {rerank_latency_ms:.0f}ms")
        
        results.append({
            "id": q_data["id"],
            "query": query,
            "category": q_data["category"],
            "expected_sections": expected,
            "baseline": {
                "sections": baseline_sections,
                "recall_at_5": b_recall,
                "mrr": b_mrr,
                "ndcg_at_5": b_ndcg
            },
            "reranked": {
                "sections": reranked_sections,
                "recall_at_5": r_recall,
                "mrr": r_mrr,
                "ndcg_at_5": r_ndcg,
                "rerank_latency_ms": round(rerank_latency_ms, 1)
            },
            "deltas": {
                "recall_at_5": recall_diff,
                "mrr": r_mrr - b_mrr,
                "ndcg_at_5": ndcg_diff
            },
            "status": status_msg
        })
        
        # Brief cooldown between queries
        time.sleep(0.3)

    # 3. Aggregate results
    total = len(results)
    avg_b_recall = sum(r["baseline"]["recall_at_5"] for r in results) / total
    avg_b_mrr = sum(r["baseline"]["mrr"] for r in results) / total
    avg_b_ndcg = sum(r["baseline"]["ndcg_at_5"] for r in results) / total
    
    avg_r_recall = sum(r["reranked"]["recall_at_5"] for r in results) / total
    avg_r_mrr = sum(r["reranked"]["mrr"] for r in results) / total
    avg_r_ndcg = sum(r["reranked"]["ndcg_at_5"] for r in results) / total
    
    improved_count = sum(1 for r in results if r["status"] == "IMPROVED")
    regressed_count = sum(1 for r in results if r["status"] == "REGRESSED")
    stable_count = sum(1 for r in results if r["status"] == "STABLE")
    
    avg_rerank_lat = sum(r["reranked"]["rerank_latency_ms"] for r in results) / total
    
    # 4. Project Full-Benchmark gains
    # We select 30 failures from a total failure pool.
    # Total queries in benchmark = 120.
    # Number of failures in baseline = 43 (approx, based on overall Recall@5 of 0.624 -> 37.6% of 120 = 45 failures).
    # Baseline benchmark overall Recall@5 = 0.624 (75 queries passed, 45 failed).
    # If the average Recall@5 improvement on the failure sample is Delta_Recall_Fail,
    # the estimated new benchmark Recall@5 will be:
    # New_Recall = Baseline_Recall + (45 / 120) * Delta_Recall_Fail
    baseline_overall_recall = report["summary"]["avg_recall_at_5"]
    baseline_overall_ndcg = report["summary"]["avg_ndcg_at_5"]
    
    failure_fraction = len(failures) / report["summary"]["total_queries"]
    delta_recall_fail = avg_r_recall - avg_b_recall
    delta_ndcg_fail = avg_r_ndcg - avg_b_ndcg
    
    projected_recall = baseline_overall_recall + failure_fraction * delta_recall_fail
    projected_ndcg = baseline_overall_ndcg + failure_fraction * delta_ndcg_fail
    
    # Print Comparative Report
    print("\n" + "=" * 80)
    print("  CONTROLLED EXPERIMENT COMPARATIVE REPORT (30 Failure Queries)")
    print("=" * 80)
    print(f"  Metric       | Baseline | Reranked | Delta  | % Change")
    print(f"  -------------|----------|----------|--------|---------")
    print(f"  Recall@5     |  {avg_b_recall:.3f}   |  {avg_r_recall:.3f}   | {delta_recall_fail:+.3f} | {((avg_r_recall-avg_b_recall)/(avg_b_recall+1e-9))*100:+.1f}%")
    print(f"  MRR          |  {avg_b_mrr:.3f}   |  {avg_r_mrr:.3f}   | {avg_r_mrr-avg_b_mrr:+.3f} | {((avg_r_mrr-avg_b_mrr)/(avg_b_mrr+1e-9))*100:+.1f}%")
    print(f"  NDCG@5       |  {avg_b_ndcg:.3f}   |  {avg_r_ndcg:.3f}   | {delta_ndcg_fail:+.3f} | {((avg_r_ndcg-avg_b_ndcg)/(avg_b_ndcg+1e-9))*100:+.1f}%")
    print(f"  -------------|----------|----------|--------|---------")
    print(f"  Avg Rerank Latency: {avg_rerank_lat:.1f} ms")
    
    print("\n  === Query-Level Breakdown ===")
    print(f"  Improved:  {improved_count} queries ({improved_count/total*100:.1f}%)")
    print(f"  Regressed: {regressed_count} queries ({regressed_count/total*100:.1f}%)")
    print(f"  Stable:    {stable_count} queries ({stable_count/total*100:.1f}%)")
    
    print("\n  === Projected Full-Benchmark Gains (120 Queries) ===")
    print(f"  Metric       | Baseline | Projected | Delta")
    print(f"  -------------|----------|-----------|--------")
    print(f"  Recall@5     |  {baseline_overall_recall:.3f}   |   {projected_recall:.3f}   | {projected_recall-baseline_overall_recall:+.3f}")
    print(f"  NDCG@5       |  {baseline_overall_ndcg:.3f}   |   {projected_ndcg:.3f}   | {projected_ndcg-baseline_overall_ndcg:+.3f}")
    print("=" * 80)
    
    # Save Report
    output_dir = Path("evaluation/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_out_path = output_dir / "reranker_experiment_report.json"
    
    report_data = {
        "summary": {
            "sample_size": total,
            "avg_rerank_latency_ms": round(avg_rerank_lat, 1),
            "improved_count": improved_count,
            "regressed_count": regressed_count,
            "stable_count": stable_count,
            "metrics": {
                "baseline": {
                    "recall_at_5": round(avg_b_recall, 3),
                    "mrr": round(avg_b_mrr, 3),
                    "ndcg_at_5": round(avg_b_ndcg, 3)
                },
                "reranked": {
                    "recall_at_5": round(avg_r_recall, 3),
                    "mrr": round(avg_r_mrr, 3),
                    "ndcg_at_5": round(avg_r_ndcg, 3)
                },
                "deltas": {
                    "recall_at_5": round(delta_recall_fail, 3),
                    "mrr": round(avg_r_mrr - avg_b_mrr, 3),
                    "ndcg_at_5": round(delta_ndcg_fail, 3)
                }
            },
            "projected_overall": {
                "recall_at_5": {
                    "baseline": round(baseline_overall_recall, 3),
                    "projected": round(projected_recall, 3),
                    "delta": round(projected_recall - baseline_overall_recall, 3)
                },
                "ndcg_at_5": {
                    "baseline": round(baseline_overall_ndcg, 3),
                    "projected": round(projected_ndcg, 3),
                    "delta": round(projected_ndcg - baseline_overall_ndcg, 3)
                }
            }
        },
        "query_results": results
    }
    
    with open(report_out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n[SAVED] Experiment comparative report saved to: {report_out_path}")
    print("=" * 80)

if __name__ == "__main__":
    run_experiment()
