import re
import httpx
from typing import List, Optional
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings
from app.core.query_expander import expand_query
from app.models import RetrievedDocument
from app.utils import get_logger

logger = get_logger(__name__)

HF_EMBEDDING_URL = "https://router.huggingface.co/hf-inference/models/intfloat/multilingual-e5-base/pipeline/feature-extraction"


class DocumentRetriever:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self._client: Optional[QdrantClient] = None
        self._init_bm25()

    # --------------------------------------------------
    # BM25 Initialization
    # --------------------------------------------------
    def _init_bm25(self):
        logger.info("initializing_bm25_searcher")
        import json
        from pathlib import Path
        from rank_bm25 import BM25Okapi

        ipc_path = Path(__file__).parent.parent.parent / "data" / "ipc_clean.json"
        with open(ipc_path, "r", encoding="utf-8") as f:
            self.ipc_docs = json.load(f)

        self.ipc_by_section = {str(doc["section_number"]): doc for doc in self.ipc_docs}

        # Tokenize all documents over section number + title + text
        doc_tokens = []
        for doc in self.ipc_docs:
            full_text = f"section {doc.get('section_number', '')} {doc.get('title', '')} {doc.get('text', '')}"
            doc_tokens.append(self._tokenize_text(full_text))

        self.bm25 = BM25Okapi(doc_tokens)
        logger.info("bm25_searcher_initialized", total_docs=len(self.ipc_docs))

    def _tokenize_text(self, text: str) -> List[str]:
        # Lowercase and extract alphanumeric words
        return re.findall(r'[a-z0-9]+', text.lower())

    # --------------------------------------------------
    # Qdrant client (CLOUD SAFE)
    # --------------------------------------------------
    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            logger.info("connecting_qdrant_cloud")
            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=20.0,
            )
        return self._client

    # --------------------------------------------------
    # Embedding via HuggingFace Inference API
    # --------------------------------------------------
    def _get_embedding(self, text: str) -> List[float]:
        # Prepend query: prefix as required by E5
        query_text = text if text.startswith("query: ") else f"query: {text}"
        headers = {"Content-Type": "application/json"}

        # Use HF token if available (handles rate-limited endpoints)
        if settings.HF_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.HF_API_TOKEN}"

        payload = {
            "inputs": query_text[:512],
            "options": {"wait_for_model": True},
        }

        import time
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        HF_EMBEDDING_URL,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                result = response.json()
                break
            except Exception as e:
                if attempt == max_attempts - 1:
                    logger.error("hf_embedding_failed", error=str(e))
                    raise
                logger.warning("hf_embedding_retry", attempt=attempt+1, error=str(e))
                time.sleep(1.0)

        # HF returns nested list for batched or flat list for single
        if isinstance(result[0], list):
            vector = result[0]
        else:
            vector = result

        # Normalize manually (same as normalize_embeddings=True)
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector

    # --------------------------------------------------
    # Detect IPC sections in query
    # --------------------------------------------------
    def detect_sections(self, query: str) -> List[str]:
        pattern = r"(?:section|sec\.?|u/s|धारा|कलम)\s*([0-9]{1,3}[A-Z]?)"
        matches = re.findall(pattern, query, flags=re.IGNORECASE)
        return list(set(matches))

    # --------------------------------------------------
    # Exact section match search
    # --------------------------------------------------
    def search_by_section(self, section: str) -> List[RetrievedDocument]:
        import time
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                results, _ = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="section_number",
                                match=MatchValue(value=str(section)),
                            )
                        ]
                    ),
                    limit=5,
                    with_payload=True,
                )
                break
            except Exception as e:
                if attempt == max_attempts - 1:
                    logger.error("qdrant_scroll_failed", error=str(e))
                    raise
                logger.warning("qdrant_scroll_retry", attempt=attempt+1, error=str(e))
                time.sleep(1.0)

        return [
            RetrievedDocument(
                section=p.payload.get("section_number"),
                title=p.payload.get("title"),
                text=p.payload.get("text"),
                score=1.0,
            )
            for p in results
        ]

    # --------------------------------------------------
    # Semantic search
    # --------------------------------------------------
    def semantic_search(self, query: str, top_k: int) -> List[RetrievedDocument]:
        vector = self._get_embedding(query)

        import time
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    limit=top_k,
                )
                results = response.points
                break
            except Exception as e:
                if attempt == max_attempts - 1:
                    logger.error("qdrant_query_failed", error=str(e))
                    raise
                logger.warning("qdrant_query_retry", attempt=attempt+1, error=str(e))
                time.sleep(1.0)

        return [
            RetrievedDocument(
                section=r.payload.get("section_number"),
                title=r.payload.get("title"),
                text=r.payload.get("text"),
                score=r.score,
            )
            for r in results
        ]

    # --------------------------------------------------
    # Sparse BM25 Search
    # --------------------------------------------------
    def bm25_search(self, query: str, top_k: int) -> List[RetrievedDocument]:
        tokens = self._tokenize_text(query)
        scores = self.bm25.get_scores(tokens)

        # Zip documents with scores and sort
        doc_scores = list(zip(self.ipc_docs, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Normalize scores to fit in [0, 1] range as required by RetrievedDocument validator
        max_score = max(scores) if len(scores) > 0 else 0.0
        denominator = max_score if max_score > 0.0 else 1.0

        results = []
        for doc, score in doc_scores[:top_k]:
            results.append(
                RetrievedDocument(
                    section=str(doc["section_number"]),
                    title=doc.get("title"),
                    text=doc.get("text"),
                    score=float(score) / denominator,
                )
            )
        return results

    # --------------------------------------------------
    # Reciprocal Rank Fusion (RRF)
    # --------------------------------------------------
    def reciprocal_rank_fusion(
        self,
        dense_results: List[RetrievedDocument],
        sparse_results: List[RetrievedDocument],
        k: int,
        top_k: int,
    ) -> List[RetrievedDocument]:
        rrf_scores = {}
        docs = {}

        # Rank elements in dense search results
        for rank, doc in enumerate(dense_results, 1):
            sec = doc.section
            docs[sec] = doc
            rrf_scores[sec] = rrf_scores.get(sec, 0.0) + 1.0 / (k + rank)

        # Rank elements in sparse BM25 search results
        for rank, doc in enumerate(sparse_results, 1):
            sec = doc.section
            docs[sec] = doc
            rrf_scores[sec] = rrf_scores.get(sec, 0.0) + 1.0 / (k + rank)

        # Sort combined results by RRF score descending
        sorted_sections = sorted(rrf_scores.keys(), key=lambda s: rrf_scores[s], reverse=True)

        fused_results = []
        for sec in sorted_sections[:top_k]:
            original_doc = docs[sec]
            fused_results.append(
                RetrievedDocument(
                    section=original_doc.section,
                    title=original_doc.title,
                    text=original_doc.text,
                    score=rrf_scores[sec],
                )
            )
        return fused_results

    # --------------------------------------------------
    # Hybrid retrieval (PRODUCTION LOGIC)
    # --------------------------------------------------
    def hybrid_search(self, query: str) -> List[RetrievedDocument]:
        sections = self.detect_sections(query)

        # Exact section lookup logic remains preserved
        if sections:
            logger.info("section_detected", sections=sections)
            docs: List[RetrievedDocument] = []
            for sec in sections:
                docs.extend(self.search_by_section(sec))
            if docs:
                return docs

        # Static query expansion (deterministic, no API calls)
        expanded_query = expand_query(query)

        logger.info("running_rrf_hybrid_search")

        # Parallel dense and sparse BM25 retrieval using expanded query
        dense_docs = self.semantic_search(expanded_query, top_k=settings.DENSE_CANDIDATES)
        bm25_docs = self.bm25_search(expanded_query, top_k=settings.BM25_CANDIDATES)

        # Merge results using RRF
        fused_docs = self.reciprocal_rank_fusion(
            dense_results=dense_docs,
            sparse_results=bm25_docs,
            k=settings.RRF_K,
            top_k=settings.DEFAULT_TOP_K,
        )

        return fused_docs


@lru_cache
def get_retriever() -> DocumentRetriever:
    return DocumentRetriever()