import re
import httpx
from typing import List, Optional
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings
from app.models import RetrievedDocument
from app.utils import get_logger

logger = get_logger(__name__)

HF_EMBEDDING_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/intfloat/multilingual-e5-base"


class DocumentRetriever:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self._client: Optional[QdrantClient] = None

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
        headers = {"Content-Type": "application/json"}

        # Use HF token if available (handles rate-limited endpoints)
        if settings.HF_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.HF_API_TOKEN}"

        payload = {
            "inputs": text[:512],
            "options": {"wait_for_model": True},
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                HF_EMBEDDING_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        result = response.json()

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

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )

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
    # Hybrid retrieval (PRODUCTION LOGIC)
    # --------------------------------------------------
    def hybrid_search(self, query: str) -> List[RetrievedDocument]:
        sections = self.detect_sections(query)

        if sections:
            logger.info("section_detected", sections=sections)
            docs: List[RetrievedDocument] = []
            for sec in sections:
                docs.extend(self.search_by_section(sec))
            if docs:
                return docs

        logger.info("fallback_to_semantic_search")
        return self.semantic_search(query, settings.DEFAULT_TOP_K)


@lru_cache
def get_retriever() -> DocumentRetriever:
    return DocumentRetriever()